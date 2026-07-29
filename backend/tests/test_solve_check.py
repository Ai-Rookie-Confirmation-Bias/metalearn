"""solve_check 단위 테스트 — 검수 응답 해석 로직(LLM 호출은 스텁).

회귀 방지 대상(실측): 기계 게이트 3개를 전부 통과했지만 보기 4개가 모두
정답이던 문항. "교체 전략의 예시로 제시된 것은? ▶FIFO/OPT/LRU/LFU"
"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.features.problems import solve_check  # noqa: E402
from app.features.problems.schemas import Problem  # noqa: E402

SOURCE = "교체 전략: 기존 데이터를 교체 ex. FIFO, OPT, LRU, LFU, NUR"


def _problem(options: list[str] | None = None, answer: str = "FIFO") -> Problem:
    return Problem(
        level=2,
        question="교체 전략의 예시로 제시된 것은?",
        options=options or ["FIFO", "OPT", "LRU", "LFU"],
        answer=answer,
        explanation="원문에 예시로 나열됨",
        source_evidence="ex. FIFO, OPT, LRU, LFU, NUR",
    )


class _StubLLM:
    """지정한 JSON을 그대로 돌려주는 검수 LLM 스텁."""

    def __init__(self, payload: object) -> None:
        self.payload = payload

    async def generate(self, prompt: str, **kwargs: object) -> str:
        if isinstance(self.payload, Exception):
            raise self.payload
        return json.dumps(self.payload, ensure_ascii=False)

    async def embed(self, text: str) -> list[float]:
        return []


def _run(payload: object, problems: list[Problem]):
    return asyncio.run(
        solve_check.verify_problems(_StubLLM(payload), problems, SOURCE)
    )


def test_multi_answer_rejected():
    # 검수가 다른 보기도 정답이라고 지목 → 정답 비유일로 폐기.
    passed, reasons = _run(
        {"items": [{"id": 0, "answer": "FIFO", "also_correct": ["OPT", "LRU"]}]},
        [_problem()],
    )
    assert passed == [] and len(reasons) == 1
    assert "비유일" in reasons[0]


def test_reviewer_picked_different_answer_rejected():
    passed, reasons = _run(
        {"items": [{"id": 0, "answer": "LRU", "also_correct": []}]}, [_problem()]
    )
    assert passed == [] and "다른 보기" in reasons[0]


def test_unanswerable_rejected():
    passed, reasons = _run(
        {"items": [{"id": 0, "answer": "", "unanswerable": True}]}, [_problem()]
    )
    assert passed == [] and "특정할 수 없" in reasons[0]


def test_clean_problem_passes():
    passed, reasons = _run(
        {"items": [{"id": 0, "answer": "FIFO", "also_correct": []}]}, [_problem()]
    )
    assert len(passed) == 1 and reasons == []


def test_notation_difference_tolerated():
    # 출제 정답은 풀네임, 검수 답은 약어 — 표기 차이로 멀쩡한 문항을 버리면 안 된다.
    p = _problem(
        options=["FIFO(First In First Out)", "OPT", "LRU", "LFU"],
        answer="FIFO(First In First Out)",
    )
    passed, _ = _run(
        {"items": [{"id": 0, "answer": "FIFO", "also_correct": []}]}, [p]
    )
    assert len(passed) == 1


def test_llm_failure_passes_all():
    # 관대 통과(net-additive) — 검증이 죽었다고 생성 결과를 버리지 않는다.
    passed, reasons = _run(RuntimeError("boom"), [_problem()])
    assert len(passed) == 1 and reasons == []


def test_missing_row_passes():
    # 검수가 빠뜨린 문항은 관대 통과.
    passed, reasons = _run({"items": []}, [_problem()])
    assert len(passed) == 1 and reasons == []


def test_answer_hidden_from_reviewer():
    # 프롬프트에 출제 정답·해설이 새면 검수가 그대로 베껴 검증이 무의미해진다.
    prompt = solve_check.build_prompt([_problem()], SOURCE)
    assert "원문에 예시로 나열됨" not in prompt  # explanation 미노출
    assert "정답" not in prompt.split("[문항들]")[1]  # 문항부에 정답 표기 없음


def _main() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {t.__name__}  {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(_main())
