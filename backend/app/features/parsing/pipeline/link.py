"""18단계 — 자료끼리 개념 잇기. 임베딩 최근접 + 회색지대만 LLM.

PPT에는 "서브넷"이라는 표제어만 있고 교재에는 그 설명이 세 쪽 있다. 이걸 이어야
**"교수님 PPT 순서로 가되 설명은 교재에서"** 가 된다. 이 서비스가 하려는 것의
본체이고, 지금까지 그 자리가 비어 있었다.

**문서쌍 단위로 저장한다.** 코스가 아니라. 문서가 공용이라 같은 두 책을 쓰는
다음 사람이 다시 계산하지 않아도 되고, 뼈대/본문 역할은 코스마다 뒤집히므로
방향을 여기 박으면 안 된다. 무방향으로 저장하고(항상 a<b) 방향은 코스가 정한다.

**문턱은 실측이다.** pilgi 452개를 ryan 578개에 전부 대조했다:

    0.85 이상   도커↔Docker, 트랜잭션↔트랜잭션, 생성패턴↔생성패턴     같은 개념
    0.75~0.85   MVC↔모델-뷰-컨트롤러, IDS↔침입탐지, 어댑터↔어댑터패턴  같거나 상하위
    0.70~0.75   정규화↔정규화(맞음) 와 블루스나프↔블루버그(틀림)가 섞임
    0.70 미만   MD4↔MD5, 자료구조↔데이터베이스                    못 씀

0.70~0.75는 **이름만 닮은 딴것**이 섞여 임베딩으로 못 가른다. 정의를 붙여
LLM에게 묻는다. 여기서 놓쳐도 연결이 하나 덜 생길 뿐이라 필터로 안전하다.

dedup의 0.92를 쓰지 않는 이유: 그건 한 문서 안 **동일 개념 병합**이라 보수적
이어야 한다(틀리면 개념이 사라진다). 여기는 "설명을 가져올 만한가"라 상위 개념
설명도 쓸모가 있고, 틀려도 설명이 하나 잘못 붙을 뿐이다.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.llm.solar import solar_client
from app.features.parsing.models import Concept, ConceptLink, DocumentPair
from app.features.parsing.prompts import link as prompt

_log = logging.getLogger("uvicorn.error")


@dataclass
class LinkResult:
    pairs_scanned: int = 0
    same: int = 0        # 0.85 이상 — 임베딩만으로 확정
    related: int = 0     # 0.75~0.85 — 상하위 포함
    judged: int = 0      # 0.70~0.75 — LLM이 같다고 한 것
    llm_calls: int = 0


def _ordered(a: uuid.UUID, b: uuid.UUID) -> tuple[uuid.UUID, uuid.UUID]:
    """무방향 저장 규칙. (x,y)와 (y,x)가 따로 쌓이면 안 된다."""
    return (a, b) if str(a) < str(b) else (b, a)


class ConceptLinker:
    def __init__(self, db: Session) -> None:
        self.db = db

    def pair_done(self, a: uuid.UUID, b: uuid.UUID) -> bool:
        """이미 계산한 문서쌍인가.

        `concept_links`가 비어 있는 게 "아직 안 쟀다"인지 "재봤는데 안 겹친다"
        인지 구별해야 한다. 없으면 코스를 열 때마다 개념 수만큼 조회를 다시 돈다.
        """
        first, second = _ordered(a, b)
        return self.db.scalar(
            select(DocumentPair.id).where(
                DocumentPair.document_a_id == first,
                DocumentPair.document_b_id == second,
            )
        ) is not None

    async def link_pair(
        self, a: uuid.UUID, b: uuid.UUID, *, force: bool = False
    ) -> LinkResult:
        """문서 둘의 개념을 잇는다. 이미 했으면 건너뛴다."""
        first, second = _ordered(a, b)
        if not force and self.pair_done(first, second):
            return LinkResult()

        result = LinkResult()
        source = self._concepts(first)
        if not source or not self._has_concepts(second):
            self._mark_done(first, second, 0)
            return result

        gray: list[tuple[Concept, Concept, float]] = []
        rows: list[ConceptLink] = []
        seen: set[tuple[uuid.UUID, uuid.UUID]] = set()

        for concept in source:
            match, similarity = self._nearest(concept, second)
            if match is None or similarity < settings.LINK_JUDGE_SIM:
                continue
            result.pairs_scanned += 1
            key = _ordered(concept.id, match.id)
            if key in seen:
                continue

            if similarity >= settings.LINK_SAME_SIM:
                kind, result.same = "same", result.same + 1
            elif similarity >= settings.LINK_RELATED_SIM:
                kind, result.related = "related", result.related + 1
            else:
                gray.append((concept, match, similarity))
                continue
            seen.add(key)
            rows.append(self._row(key, similarity, kind, "embed"))

        confirmed = await self._judge(gray, result)
        for concept, match, similarity in confirmed:
            key = _ordered(concept.id, match.id)
            if key in seen:
                continue
            seen.add(key)
            rows.append(self._row(key, similarity, "same", "llm"))

        self._insert(rows)
        self._mark_done(first, second, len(rows))
        _log.info(
            "개념 연결: %d쌍 검토 → same %d · related %d · LLM확정 %d (호출 %d)",
            result.pairs_scanned, result.same, result.related,
            result.judged, result.llm_calls,
        )
        return result

    # ── 내부 ──────────────────────────────────────────────────────

    def _concepts(self, document_id: uuid.UUID) -> list[Concept]:
        return list(
            self.db.scalars(
                select(Concept).where(
                    Concept.document_id == document_id,
                    Concept.embedding.is_not(None),
                )
            )
        )

    def _has_concepts(self, document_id: uuid.UUID) -> bool:
        return self.db.scalar(
            select(Concept.id)
            .where(
                Concept.document_id == document_id,
                Concept.embedding.is_not(None),
            )
            .limit(1)
        ) is not None

    def _nearest(
        self, concept: Concept, document_id: uuid.UUID
    ) -> tuple[Concept | None, float]:
        """상대 문서에서 가장 가까운 개념 하나. pgvector가 계산한다."""
        distance = Concept.embedding.cosine_distance(concept.embedding)
        row = self.db.execute(
            select(Concept, distance.label("dist"))
            .where(
                Concept.document_id == document_id,
                Concept.embedding.is_not(None),
            )
            .order_by(distance)
            .limit(1)
        ).first()
        if row is None:
            return None, 0.0
        return row[0], 1.0 - float(row[1])

    async def _judge(
        self, gray: list[tuple[Concept, Concept, float]], result: LinkResult
    ) -> list[tuple[Concept, Concept, float]]:
        """회색지대만 정의를 붙여 LLM에게 묻는다.

        실패하면 **버린다.** 여기서 놓치면 연결이 하나 덜 생길 뿐이지만,
        틀리게 이으면 엉뚱한 설명이 개념에 붙는다 — 화면에 그대로 보인다.
        """
        if not gray:
            return []
        gray = gray[: settings.LINK_MAX_JUDGE_PAIRS]
        confirmed: list[tuple[Concept, Concept, float]] = []
        batch_size = settings.LINK_JUDGE_BATCH_SIZE

        for start in range(0, len(gray), batch_size):
            batch = gray[start : start + batch_size]
            pairs = [
                (a.name, a.definition or "", b.name, b.definition or "")
                for a, b, _ in batch
            ]
            try:
                raw = await solar_client.generate_json(
                    prompt.build_prompt(pairs), system=prompt.SYSTEM
                )
                result.llm_calls += 1
                same = {
                    int(x) for x in (raw.get("same") or [])
                    if isinstance(x, int) or (isinstance(x, str) and x.isdigit())
                }
            except Exception as exc:  # noqa: BLE001 — 못 이으면 그만이다
                _log.warning("개념 연결 회색지대 판정 실패 — 버림: %s", exc)
                continue
            for offset, item in enumerate(batch):
                if offset in same:
                    confirmed.append(item)
        result.judged = len(confirmed)
        return confirmed

    def _insert(self, rows: list[ConceptLink]) -> None:
        """이미 있는 연결은 조용히 건너뛴다.

        **같은 문서쌍을 두 곳이 동시에 계산할 수 있다.** 책장 목록 한 번이
        코스를 전부 조립하는데, 그 요청이 겹치면 서로 다른 세션이 같은 쌍을
        나란히 넣는다. `seen`은 한 호출 안에서만 막아 준다.

        실측: 자료 6개짜리 수업(문서쌍 15개)에서 9쌍째에
        `duplicate key ... uq_concept_link`로 죽었고, 그 수업이 책장에서
        통째로 사라졌다(`sync_courses`가 예외를 삼키고 건너뛴다).

        연결은 무방향이라 두 번 넣어 봐야 얻을 게 없다. DB가 거르게 둔다.
        """
        if not rows:
            return
        self.db.execute(
            pg_insert(ConceptLink.__table__)
            .values(
                [
                    {
                        "id": uuid.uuid4(),
                        "concept_a_id": r.concept_a_id,
                        "concept_b_id": r.concept_b_id,
                        "similarity": r.similarity,
                        "kind": r.kind,
                        "verified_by": r.verified_by,
                    }
                    for r in rows
                ]
            )
            .on_conflict_do_nothing(constraint="uq_concept_link")
        )

    @staticmethod
    def _row(
        key: tuple[uuid.UUID, uuid.UUID], similarity: float, kind: str, by: str
    ) -> ConceptLink:
        return ConceptLink(
            concept_a_id=key[0], concept_b_id=key[1],
            similarity=similarity, kind=kind, verified_by=by,
        )

    def _mark_done(self, a: uuid.UUID, b: uuid.UUID, count: int) -> None:
        existing = self.db.scalar(
            select(DocumentPair).where(
                DocumentPair.document_a_id == a, DocumentPair.document_b_id == b
            )
        )
        if existing is not None:
            existing.link_count = count
            return
        self.db.add(
            DocumentPair(document_a_id=a, document_b_id=b, link_count=count)
        )
