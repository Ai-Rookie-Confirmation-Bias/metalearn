"""12.5 분야 판정을 이미 파싱된 문서에 소급 적용한다.

12.5단계가 파이프라인에 들어오기 전에 파싱된 문서는 field/prereq_probe가 비어
있다. 재파싱은 Document Parse 비용이 크고(문서당 수십 초) 결과가 달라질 수도
있어서, 이 단계만 따로 돌린다.

    docker compose exec backend uv run python -m scripts.backfill_field
    docker compose exec backend uv run python -m scripts.backfill_field --force
    docker compose exec backend uv run python -m scripts.backfill_field --runs 5

--runs로 회차를 늘리면 재현성을 눈으로 확인할 수 있다. 저장은 하지 않고
회차별 결과만 찍는 --dry-run과 같이 쓰면 검증용이 된다.
"""
from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.llm.solar import solar_client
from app.features.parsing.models import DocStatus, Document
from app.features.parsing.pipeline import field
from app.features.parsing.prompts import field as field_prompt
from app.features.parsing.repository import ParsingRepository


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="이미 채워진 것도 다시")
    parser.add_argument("--runs", type=int, default=None, help="호출 회차 (기본 2)")
    parser.add_argument("--dry-run", action="store_true", help="저장하지 않음")
    args = parser.parse_args()

    db = SessionLocal()
    repo = ParsingRepository(db)
    try:
        documents = list(
            db.scalars(
                select(Document)
                .where(Document.status == DocStatus.READY.value)
                .order_by(Document.created_at)
            )
        )
        for document in documents:
            if document.prereq_probe and not args.force:
                print(f"건너뜀 (이미 있음): {document.filename}")
                continue

            titles, concepts, dangling = repo.field_probe_inputs(
                document.id,
                top_concepts=field_prompt.TOP_CONCEPTS,
                top_dangling=field_prompt.TOP_DANGLING,
            )
            probe = await field.probe(
                filename=document.filename,
                topics=titles,
                concepts=concepts,
                dangling=dangling,
                runs=args.runs,
            )

            print(f"\n{'=' * 74}\n{document.filename}")
            print(f"  분야: {probe.field}  ({probe.level})")
            if not probe.subjects:
                print("  선수 과목 없음 — 밑바닥부터 다 가르치는 자료")
            for subject in probe.subjects:
                mark = "순서 있음" if subject.ordered else "순서 없음"
                print(f"  · {subject.name} [{mark}] — {subject.why}")
                for item in subject.subtopics:
                    print(f"      ☐ {item}")

            if not args.dry_run:
                document.field = probe.field or None
                document.prereq_probe = probe.as_dict()
                db.commit()
    finally:
        db.close()
        await solar_client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
