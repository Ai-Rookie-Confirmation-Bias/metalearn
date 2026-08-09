"""저장된 문제은행 재검증 감사 — 생성 때 통과한 문항을 배심원단에 다시 세운다.

DB는 읽기만 한다(삭제·수정 없음). 수정 루프도 끈다 — 목적이 "고치기"가 아니라
"저장분 중 실사용 가능 비율"(QUIZ_TUNING의 품질 지표) 측정이기 때문.

    docker exec metalearn-1-backend-1 uv run python scripts/reverify_quiz.py \
        --doc <document_id> --since 2026-08-08
"""
import argparse
import asyncio
import collections
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.database import SessionLocal  # noqa: E402
from app.core.llm.solar import solar_client  # noqa: E402
from app.core.quality import CandidateItem, QualityConfig, validate_items  # noqa: E402
from app.features.quiz.models import QuizItem  # noqa: E402


async def main(document_id: uuid.UUID, since_raw: str) -> None:
    # created_at은 timestamptz — 문자열 그대로 비교하면 psycopg 타입 에러
    since = datetime.fromisoformat(since_raw)
    if since.tzinfo is None:
        since = since.replace(tzinfo=timezone.utc)
    db = SessionLocal()
    try:
        rows = (
            db.execute(
                select(QuizItem)
                .where(QuizItem.document_id == document_id, QuizItem.created_at >= since)
                .order_by(QuizItem.created_at, QuizItem.id)
            )
            .scalars()
            .all()
        )
    finally:
        db.close()
    if not rows:
        print(f"대상 없음: doc={document_id} since={since}")
        return
    print(f"재검증 대상 {len(rows)}문항 (created_at >= {since})")

    verify_llm = None
    if settings.EXAONE_API_KEY:
        from app.core.llm.exaone import exaone_client

        verify_llm = exaone_client
        print("배심원단: Solar(1차) + EXAONE(2차)")
    else:
        print("배심원단: Solar 단독 (EXAONE 키 없음)")

    candidates = [
        CandidateItem(type=r.type, data=r.data, evidence_text=(r.evidence or {}).get("text", ""))
        for r in rows
    ]
    config = QualityConfig(enable_revise=False)  # 감사 — 고치지 않고 판정만

    # 1패스: 유형별로 정렬해 균질 배치로 — mcq·OX·단답이 한 배치에 섞이면
    # 풀이자 응답 형식이 흔들린다 (151문항 감사 실측). 판정은 원래 순서로 복원.
    order = sorted(range(len(candidates)), key=lambda i: (candidates[i].type, i))
    sorted_verdicts = await validate_items(
        [candidates[i] for i in order],
        solar_client,
        config,
        revise_llm=None,
        second_llm=verify_llm,
    )
    verdicts = [None] * len(candidates)
    for pos, orig in enumerate(order):
        verdicts[orig] = sorted_verdicts[pos]
    first_pass = sum(1 for v in verdicts if v.ok)
    print(f"1패스(배치 {config.batch_size}): {first_pass}/{len(rows)} 통과")

    # 2패스: 탈락분만 배치 1로 재판정 — 배치 오염(답 밀림·형식 난조)을 배제한
    # 최종 판정. 문항 결함이 진짜라면 혼자 물어봐도 똑같이 떨어진다.
    failed_idx = [i for i, v in enumerate(verdicts) if not v.ok]
    if failed_idx:
        print(f"2패스(배치 1): 탈락 {len(failed_idx)}건 재확인 중…")
        solo = QualityConfig(enable_revise=False, batch_size=1)
        re_verdicts = await validate_items(
            [candidates[i] for i in failed_idx],
            solar_client,
            solo,
            revise_llm=None,
            second_llm=verify_llm,
        )
        revived = 0
        for i, v in zip(failed_idx, re_verdicts):
            if v.ok:
                revived += 1
            verdicts[i] = v  # 최종 판정 = 2패스
        print(f"2패스에서 회생: {revived}건 (1패스 탈락이 배치 오염이었던 것)")

    passed = sum(1 for v in verdicts if v.ok)
    print(f"\n최종: {passed}/{len(rows)} 통과 ({passed * 100 // len(rows)}%)")

    by_stage = collections.Counter(v.stage for v in verdicts if not v.ok)
    if by_stage:
        print("탈락 단계 분포:", dict(by_stage))
        print("\n-- 탈락 문항 --")
        for r, v in zip(rows, verdicts):
            if v.ok:
                continue
            stem = (
                r.data.get("question")
                or r.data.get("statement")
                or r.data.get("prompt")
                or "(cloze)"
            )
            print(f"[{v.stage}] {r.toc_index}·{r.type}·{r.concept_name}: {str(stem)[:46]}")
            print(f"    사유: {v.reason[:100]}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--doc", required=True, help="document_id (UUID)")
    ap.add_argument("--since", default="2026-08-08", help="이 시각 이후 저장분만")
    args = ap.parse_args()
    asyncio.run(main(uuid.UUID(args.doc), args.since))
