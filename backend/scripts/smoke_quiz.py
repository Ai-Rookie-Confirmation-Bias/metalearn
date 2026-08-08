"""문제 생성 스모크 테스트 — 실제 Solar 호출로 문항 품질을 눈으로 확인.

DB·도커 불필요. backend/.env에 UPSTAGE_API_KEY만 있으면 된다.

    cd backend
    uv run python scripts/smoke_quiz.py                # 조각 1개, 예산 6문항 (기본)
    uv run python scripts/smoke_quiz.py --chunks 3 --budget 20   # 더 크게
"""
import argparse
import asyncio
import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.llm.solar import solar_client  # noqa: E402
from app.features.quiz.schemas import ParsedDocument, QuizGenConfig  # noqa: E402
from app.features.quiz.service import QuizService  # noqa: E402

FIXTURE = Path(__file__).parent.parent / "tests" / "fixtures" / "parsed_sample.json"


class MemRepo:
    rows: list = []

    def replace_document_items(self, course_id, document_id, items) -> None:
        MemRepo.rows = items


async def main(n_chunks: int, budget: int, verifier: str = "solar") -> None:
    doc = ParsedDocument.model_validate(json.loads(FIXTURE.read_text(encoding="utf-8")))

    # 앞에서 n_chunks개 조각만 사용 (비용 제한)
    keep = {c.index for c in doc.chunks[:n_chunks]}
    doc = doc.model_copy(
        update={
            "chunks": [c for c in doc.chunks if c.index in keep],
            "tocs": [
                t.model_copy(update={"chunk_indexes": [i for i in t.chunk_indexes if i in keep]})
                for t in doc.tocs
                if any(i in keep for i in t.chunk_indexes)
            ],
        }
    )
    config = QuizGenConfig(toc_min=budget, toc_max=budget, overgen_ratio=1.0)

    svc = QuizService.__new__(QuizService)
    svc.repo = MemRepo()
    svc.llm = solar_client
    svc.verify_llm = None
    if verifier in ("jury", "exaone"):  # exaone = 구버전 표기 호환
        from app.core.config import settings
        from app.core.llm.exaone import exaone_client

        if not settings.EXAONE_API_KEY:
            raise SystemExit("EXAONE_API_KEY가 .env에 없습니다 (UTF-8 인코딩 주의)")
        svc.verify_llm = exaone_client

    label = "배심원단 (심판·풀이 Solar+EXAONE)" if svc.verify_llm else "Solar 단일"
    print(f"조각 {len(doc.chunks)}개 · 목차당 예산 {budget}문항 · {label} — 호출 시작…\n")
    result = await svc.generate_bank(uuid.uuid4(), uuid.uuid4(), doc, config=config)

    print(f"{'=' * 60}\n저장된 문항: {result.saved}개 · 폐기: {len(result.discarded)}건\n")
    for d in result.discarded:
        print(f"  ✗ {d}")

    if result.discarded_items:
        print(f"\n{'=' * 60}\n폐기 문항 내용 ({len(result.discarded_items)}건):")
        for i, d in enumerate(result.discarded_items):
            print(f"\n{'─' * 60}")
            print(f"✗[{i + 1}] {d['type']} · {d['concept']}")
            print(f"사유: {d['reason']}")
            print(json.dumps(d["data"], ensure_ascii=False, indent=2))

    for i, r in enumerate(MemRepo.rows):
        print(f"\n{'─' * 60}")
        print(f"[{i + 1}] {r.type} · {r.concept_name} · 난이도 {r.difficulty} · 목차 {r.toc_index}")
        print(json.dumps(r.data, ensure_ascii=False, indent=2))
        print(f"📎 근거 (p.{r.evidence['pageFrom']}): {r.evidence['text'][:150]}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--chunks", type=int, default=1, help="사용할 조각 수 (기본 1)")
    ap.add_argument("--budget", type=int, default=6, help="목차당 문항 예산 (기본 6)")
    ap.add_argument(
        "--verifier",
        choices=["solar", "jury", "exaone"],
        default="solar",
        help="solar=단독 / jury=배심원단(Solar+EXAONE 심판·풀이, exaone은 구표기)",
    )
    args = ap.parse_args()
    asyncio.run(main(args.chunks, args.budget, args.verifier))
