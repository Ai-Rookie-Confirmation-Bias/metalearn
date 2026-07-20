"""[3.Service 보조] external_refs 수집 — ai_prereq 개념의 외부 근거 (ISSUE-017 ②).

방침(2026-07-06 협의): LLM이 지어낸 설명을 근거로 우기지 않고, 실제 웹 출처
(URL+snippet)를 남긴다(퍼플렉시티식). 검색원은 한국어 위키백과 REST API —
무키·무료. 검색 실패 개념만 LLM 설명으로 폴백하되 source_kind='llm'으로
출처 약함을 값에 명시한다.

대상은 source='ai_prereq' 개념 전부(정본 규약). 이미 근거가 있으면 건너뛴다
(재실행 안전). external_refs 테이블/모델은 병합 정본에 이미 존재 — 여기서는
수집만 채운다. 결과 검증은 하류 faithfulness 게이트(커리큘럼 파트)가 담당.
"""
import asyncio
import logging
import re
import uuid
from urllib.parse import quote

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.llm.solar import solar_client
from app.features.seed.models import Concept, ExternalRef

_log = logging.getLogger("uvicorn.error")

_WIKI_SEARCH = "https://ko.wikipedia.org/w/rest.php/v1/search/page"
_WIKI_PAGE = "https://ko.wikipedia.org/wiki/"
# 동시 3 + 429 지수 백오프 재시도 — 위키 rate limit 예절 (실측: 동시 8로
# 반복 실행 시 429 다발 → 전부 LLM 폴백으로 밀려 출처 품질 하락)
_CONCURRENCY = 3
_RETRY_AFTER_SEC = 1.5
_RETRIES = 3
_SEARCH_LIMIT = 5  # 1위만 보면 동음이의·목록에 막힘 → 상위 후보 중 근거 가치 있는 첫 것
_TIMEOUT = 10.0
_SNIPPET_MAX = 600
_TAG_RE = re.compile(r"<[^>]+>")
# 근거 가치 없는 문서 신호 — 동음이의·목록·분류 문서는 건너뛰고 다음 후보로.
_SKIP_SIGNALS = ("동음이의", "다음을 의미한다", "다음을 가리킨다")

_FALLBACK_SYSTEM = (
    "너는 학습 개념 사전 집필자다. 각 개념을 사실 위주로 2문장으로 설명한다. "
    "출력은 지정한 JSON 스키마만 따른다."
)
_FALLBACK_BATCH = 40


def _fallback_prompt(items: list[tuple[int, str, str]]) -> str:
    lines = [
        "아래 개념들을 각각 한국어 2문장으로 설명하라. 과장·추측 금지, 정의 위주.\n",
        '출력 JSON: {"refs": [{"id": int, "snippet": str}, ...]} — 전 항목 필수.\n\n',
    ]
    for idx, name, description in items:
        lines.append(f"- id={idx}: {name} — {description}\n")
    return "".join(lines)


async def _wiki_get(client: httpx.AsyncClient, name: str) -> list[dict]:
    """위키 검색 상위 페이지들 — 429는 지수 백오프로 재시도(폴백으로 안 밀리게)."""
    for attempt in range(_RETRIES):
        resp = await client.get(_WIKI_SEARCH, params={"q": name, "limit": _SEARCH_LIMIT})
        if resp.status_code == 429 and attempt < _RETRIES - 1:
            await asyncio.sleep(_RETRY_AFTER_SEC * (2**attempt))
            continue
        resp.raise_for_status()
        return (resp.json() or {}).get("pages") or []
    return []


async def _search_wiki(client: httpx.AsyncClient, name: str) -> dict | None:
    """위키 검색 → 상위 후보 중 근거 가치 있는 첫 결과 {'title','url','snippet'}.

    1위만 보면 동음이의·목록 문서에서 미스가 잦다(히트율 19% 원인) → 상위
    _SEARCH_LIMIT개를 순회하며 스킵 신호가 없는 첫 후보를 채택.
    """
    pages = await _wiki_get(client, name)
    for page in pages:
        title = (page.get("title") or "").strip()
        excerpt = _TAG_RE.sub("", page.get("excerpt") or "").strip()
        description = (page.get("description") or "").strip()
        snippet = " — ".join(x for x in (description, excerpt) if x)[:_SNIPPET_MAX]
        if not snippet:
            continue
        blob = f"{title} {snippet}"
        if any(sig in blob for sig in _SKIP_SIGNALS) or title.endswith("목록"):
            continue  # 동음이의·목록 문서 → 다음 후보
        return {
            "title": title or name,
            "url": _WIKI_PAGE + quote(page.get("key") or title or name),
            "snippet": snippet,
        }
    return None


async def collect_external_refs(db: Session, course_id: uuid.UUID) -> dict:
    """course의 ai_prereq 개념에 근거를 채운다. 반환: 수집 통계."""
    targets = list(
        db.scalars(
            select(Concept).where(
                Concept.course_id == course_id, Concept.source == "ai_prereq"
            )
        )
    )
    if not targets:
        return {"targets": 0, "collected": 0, "web": 0, "llm_fallback": 0}
    have = set(
        db.scalars(
            select(ExternalRef.concept_id).where(
                ExternalRef.concept_id.in_([c.id for c in targets])
            )
        )
    )
    pending = [c for c in targets if c.id not in have]
    if not pending:
        return {"targets": len(targets), "collected": 0, "web": 0, "llm_fallback": 0}

    sem = asyncio.Semaphore(_CONCURRENCY)
    results: dict[uuid.UUID, dict | None] = {}

    async with httpx.AsyncClient(
        timeout=_TIMEOUT, headers={"User-Agent": "MetaLearn/0.1"}
    ) as client:

        async def fetch(concept: Concept) -> None:
            async with sem:
                try:
                    results[concept.id] = await _search_wiki(client, concept.name)
                except Exception as exc:  # noqa: BLE001 — 개별 실패는 폴백으로
                    _log.warning("위키 검색 실패(%s): %s", concept.name, exc)
                    results[concept.id] = None

        await asyncio.gather(*(fetch(c) for c in pending))

    web = 0
    misses: list[Concept] = []
    for concept in pending:
        hit = results.get(concept.id)
        if hit:
            db.add(
                ExternalRef(
                    concept_id=concept.id,
                    source_kind="web",
                    title=hit["title"][:500],
                    url=hit["url"],
                    snippet=hit["snippet"],
                )
            )
            web += 1
        else:
            misses.append(concept)

    llm_ok = 0
    for i in range(0, len(misses), _FALLBACK_BATCH):
        batch = misses[i : i + _FALLBACK_BATCH]
        try:
            raw = await solar_client.generate_json(
                _fallback_prompt([(j, c.name, c.description or "") for j, c in enumerate(batch)]),
                system=_FALLBACK_SYSTEM,
            )
            got = {
                row["id"]: str(row.get("snippet", "")).strip()
                for row in raw.get("refs") or []
                if isinstance(row, dict) and isinstance(row.get("id"), int)
                and 0 <= row["id"] < len(batch)
            }
        except Exception as exc:  # noqa: BLE001
            _log.warning("근거 LLM 폴백 배치 실패: %s", exc)
            got = {}
        for j, c in enumerate(batch):
            snippet = got.get(j) or (c.description or c.name)
            db.add(
                ExternalRef(
                    concept_id=c.id,
                    source_kind="llm",
                    title=c.name[:500],
                    url=None,
                    snippet=snippet[:_SNIPPET_MAX],
                )
            )
            llm_ok += 1

    db.flush()
    stats = {
        "targets": len(targets),
        "collected": len(pending),
        "web": web,
        "llm_fallback": llm_ok,
    }
    _log.info(
        "external_refs 수집: 대상 %d, 신규 %d (web %d / llm 폴백 %d)",
        stats["targets"], stats["collected"], web, llm_ok,
    )
    return stats
