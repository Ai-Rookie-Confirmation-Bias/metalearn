"""골든셋으로 게이트 정확도를 채점한다.

왜 필요한가: 지금까지 "폐기 4건"이라는 숫자는 있었지만, 그게 **옳은 폐기인지
과폐기인지** 알 방법이 없었다. 프롬프트를 고쳐도 좋아졌는지 판단할 수 없고,
같은 입력에도 실행마다 결과가 흔들려(실측: 총 문항 15~18, L3 0~3) 단일 실행은
근거가 되지 못한다. 라벨된 문항을 게이트에 직접 통과시키면 LLM 생성의 편차를
빼고 **게이트 자체의 정확도만** 잴 수 있다.

측정 지표
  누락(false negative) : 버려야 할 문항이 통과 — 불량이 문제은행에 들어간다
  과폐기(false positive): 살려야 할 문항이 폐기 — 문항 수가 줄고 재시도가 낭비된다
누락은 학습자에게 잘못된 지식을 심고, 과폐기는 비용을 태운다. 둘을 함께 본다.

실행
  uv run python bench/run_gates.py                 # 기계 게이트만(무료·즉시)
  uv run python bench/run_gates.py --solve-check   # 검수 LLM 게이트까지(과금)
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pydantic import ValidationError  # noqa: E402

from app.features.problems import solve_check  # noqa: E402
from app.features.problems.grounding import evidence_in_source  # noqa: E402
from app.features.problems.quality import (  # noqa: E402
    answer_leaked_in_title,
    is_free_response_style,
    strip_option_label,
)
from app.features.problems.schemas import ConceptInput, Problem  # noqa: E402

GOLDEN_DIR = Path(__file__).parent / "golden"


def _normalize(raw: dict) -> dict:
    out = dict(raw)
    if isinstance(out.get("options"), list):
        out["options"] = [strip_option_label(str(o)) for o in out["options"]]
    if isinstance(out.get("answer"), str):
        out["answer"] = strip_option_label(out["answer"])
    return out


def run_mechanical(raw: dict, concept: ConceptInput) -> tuple[str | None, Problem | None]:
    """기계 게이트 3종. 폐기면 (게이트명, None), 통과면 (None, Problem)."""
    try:
        p = Problem.model_validate(_normalize(raw))
    except ValidationError:
        return "schema", None
    if is_free_response_style(p.question) or answer_leaked_in_title(
        p.answer, concept.title
    ):
        return "quality", None
    if not evidence_in_source(p.source_evidence, concept.source_text):
        return "grounding", None
    return None, p


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--solve-check", action="store_true", help="검수 LLM 게이트 포함")
    ap.add_argument("--file", default="os_memory.json")
    args = ap.parse_args()

    data = json.loads((GOLDEN_DIR / args.file).read_text(encoding="utf-8"))
    concept = ConceptInput(**data["concept"])
    items = data["items"]

    verdicts: dict[str, str] = {}  # id -> 폐기 게이트명 또는 "pass"
    survivors: list[tuple[str, Problem]] = []

    for it in items:
        gate, problem = run_mechanical(it["problem"], concept)
        if gate:
            verdicts[it["id"]] = gate
        else:
            verdicts[it["id"]] = "pass"
            survivors.append((it["id"], problem))

    if args.solve_check and survivors:
        from app.core.llm.solar import solar_client

        kept, reasons = await solve_check.verify_problems(
            solar_client, [p for _, p in survivors], concept.source_text
        )
        kept_ids = {id(p) for p in kept}
        for gid, p in survivors:
            if id(p) not in kept_ids:
                verdicts[gid] = "solve_check"
        if reasons:
            print(f"  (검수 폐기 사유: {'; '.join(reasons)})\n")

    # ── 채점 ────────────────────────────────────────────────────────
    misses: list[dict] = []  # 버려야 하는데 통과 (누락)
    over: list[dict] = []  # 살려야 하는데 폐기 (과폐기)
    correct = 0
    by_gate: dict[str, int] = {}

    print(f"{'ID':<5} {'라벨':<5} {'판정':<12} {'결과'}")
    print("-" * 62)
    for it in items:
        gid, label = it["id"], it["label"]
        v = verdicts[gid]
        dropped = v != "pass"
        ok = dropped == (label == "drop")
        if ok:
            correct += 1
        elif label == "drop":
            misses.append(it)
        else:
            over.append(it)
        if dropped:
            by_gate[v] = by_gate.get(v, 0) + 1
        mark = "OK" if ok else ("누락" if label == "drop" else "과폐기")
        print(f"{gid:<5} {label:<5} {v:<12} {mark}")

    n = len(items)
    n_drop = sum(1 for i in items if i["label"] == "drop")
    n_pass = n - n_drop
    print("-" * 62)
    print(f"정확도 {correct}/{n}  (drop 라벨 {n_drop} / pass 라벨 {n_pass})")
    print(f"누락 {len(misses)}건 · 과폐기 {len(over)}건")
    if by_gate:
        print("게이트별 폐기: " + ", ".join(f"{g} {c}" for g, c in sorted(by_gate.items())))

    for it in misses:
        exp = it.get("expected_gate", "?")
        print(f"  [누락] {it['id']} — {it['note']}  (기대 게이트: {exp})")
    for it in over:
        print(f"  [과폐기] {it['id']} — {it['note']}  (실제 폐기: {verdicts[it['id']]})")

    if not args.solve_check:
        pending = [i["id"] for i in misses if i.get("expected_gate") == "solve_check"]
        if pending:
            print(
                f"\n※ {', '.join(pending)}는 검수 LLM 게이트가 담당한다 — "
                "--solve-check 로 다시 실행하면 잡히는지 확인할 수 있다."
            )
    return 1 if (misses or over) else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
