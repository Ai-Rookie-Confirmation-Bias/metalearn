"""8단계 — 개념 추출. Solar = 조각 수. **전체 비용의 80%.**

조각마다 1회 호출하고, 동시성은 설정값으로 제한한다. 조각 40개를 한꺼번에
던지면 즉시 429가 뜬다 (Solar 클라이언트에도 전역 세마포어가 있지만,
여기서 한 번 더 조여야 재시도 폭풍이 안 생긴다).

조각 하나가 실패해도 전체를 죽이지 않는다 — 1회 재시도하고, 그래도 안 되면
빈 결과로 넘긴다. 개념이 덜 나오는 건 품질 저하지만, 40콜 중 1개 때문에
전부 버리는 건 사고다. 실패한 조각은 로그와 반환값에 남는다.
"""
from __future__ import annotations

import asyncio
import logging

from pydantic import ValidationError

from app.core.config import settings
from app.core.llm.solar import solar_client
from app.features.parsing.prompts import concepts as prompt
from app.features.parsing.schemas import ExtractionResult, Segment

_log = logging.getLogger("uvicorn.error")


async def extract_all(
    segments: list[Segment],
    topic_titles: dict[int, str],
    sentences_by_seq: dict[int, list] | None = None,
) -> tuple[dict[int, ExtractionResult], list[int]]:
    """조각별 병렬 추출.

    sentences_by_seq를 주면 원문을 "[n] 문장"으로 번호 매겨 보여주고 개념마다
    근거 문장 번호를 함께 받는다. 5-b가 이미 나눈 문장을 그대로 쓰므로
    추가 비용이 없다.

    반환: ({조각 seq: 추출 결과}, 실패한 조각 seq 목록)
    """
    if not segments:
        return {}, []

    sem = asyncio.Semaphore(settings.EXTRACTION_MAX_CONCURRENCY)
    results: dict[int, ExtractionResult] = {}
    failed: list[int] = []
    done = 0

    async def one(segment: Segment) -> None:
        nonlocal done
        async with sem:
            title = topic_titles.get(segment.seq, "")
            texts = [s.text for s in (sentences_by_seq or {}).get(segment.seq, [])]
            try:
                result = await _extract(segment, title, texts)
            except Exception:  # noqa: BLE001 — 일시 오류 대비 1회 재시도
                _log.warning("개념 추출 실패, 재시도: 조각 #%d", segment.seq)
                try:
                    result = await _extract(segment, title, texts)
                except Exception as exc:  # noqa: BLE001
                    _log.error("개념 추출 최종 실패: 조각 #%d — %s", segment.seq, exc)
                    failed.append(segment.seq)
                    return
            _drop_unknown_evidence(result, len(texts), segment.seq)
            results[segment.seq] = result
            done += 1
            _log.info(
                "개념 추출 %d/%d: 조각 #%d — %d개",
                done, len(segments), segment.seq, len(result.concepts),
            )

    _log.info("개념 추출 시작: 조각 %d개 (동시성 %d)",
              len(segments), settings.EXTRACTION_MAX_CONCURRENCY)
    await asyncio.gather(*(one(s) for s in segments))

    counts = {seq: len(r.concepts) for seq, r in results.items()}
    total = sum(counts.values())
    cap = settings.CONCEPT_MAX_PER_SEGMENT
    over = {seq: n for seq, n in counts.items() if n > cap}
    _log.info(
        "개념 추출 완료: %d개 · 조각당 평균 %.1f (상한 %d) · 실패 조각 %d개",
        total, total / max(len(counts), 1), cap, len(failed),
    )
    if over:
        # 자르지 않는다 — 자료가 용어 나열형이면 초과가 정상일 수 있고,
        # 임의로 자르면 진짜 개념이 사라진다. 튜닝 판단용으로 남길 뿐이다.
        _log.warning(
            "개념 상한 초과 조각 %d개 (최대 %d개): %s",
            len(over), max(over.values()),
            sorted(over.items(), key=lambda x: -x[1])[:8],
        )
    return results, failed


def _drop_unknown_evidence(
    result: ExtractionResult, sentence_count: int, seq: int
) -> None:
    """존재하지 않는 문장 번호는 버린다.

    근거는 원문을 가리키는 주소다. 범위를 벗어난 번호를 그대로 저장하면
    나중에 "33p 이 문장" 표시가 엉뚱한 데를 짚거나 조용히 빈칸이 된다.
    지어낸 번호를 남기느니 근거 없음으로 두는 게 낫다.
    """
    dropped = 0

    def walk(node) -> None:
        nonlocal dropped
        valid = [i for i in node.evidence if 0 <= i < sentence_count]
        dropped += len(node.evidence) - len(valid)
        node.evidence = valid
        for child in node.prerequisites:
            walk(child)

    for root in result.concepts:
        walk(root)
    if dropped:
        _log.warning(
            "근거 문장 번호 %d개가 범위를 벗어남 (조각 #%d, 문장 %d개) — 버림",
            dropped, seq, sentence_count,
        )


async def _extract(
    segment: Segment, topic_title: str, sentences: list[str]
) -> ExtractionResult:
    body = prompt.number_sentences(sentences) if sentences else segment.content
    raw = await solar_client.generate_json(
        prompt.build_prompt(
            topic_title, segment.heading, body, numbered=bool(sentences)
        ),
        system=prompt.SYSTEM,
    )
    try:
        return ExtractionResult.model_validate(raw)
    except ValidationError as exc:
        raise ValueError(
            f"추출 JSON이 스키마 검증을 통과하지 못했습니다 (조각 #{segment.seq}): {exc}"
        ) from exc
