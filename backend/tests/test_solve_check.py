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


def test_answer_listing_all_options_rejected():
    # 검수가 also_correct를 비워둔 채 answer에 보기를 나열해 "다 정답"을 표현하는
    # 실측 사례. 관대 비교(포함 관계)가 이를 동의로 오인하던 회귀를 막는다.
    passed, reasons = _run(
        {"items": [{"id": 0, "answer": "FIFO, OPT, LRU, LFU", "also_correct": []}]},
        [_problem()],
    )
    assert passed == [] and "비유일" in reasons[0]


def test_reviewer_picked_different_answer_rejected():
    passed, reasons = _run(
        {"items": [{"id": 0, "answer": "LRU", "also_correct": []}]}, [_problem()]
    )
    assert passed == [] and "다른 답" in reasons[0]


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
    # 보기 자체는 보여야 하므로("FIFO"는 등장), **어느 것이 정답인지 표시**가
    # 없다는 것과 해설이 빠졌다는 것을 확인한다.
    p = _problem()
    prompt = solve_check.build_prompt([p], SOURCE)
    assert p.explanation not in prompt
    assert f"정답: {p.answer}" not in prompt
    assert "▶" not in prompt and "answer:" not in prompt.split("[문항들]")[1]


# ── 신규 유형(multi·ox·order) 검수 ────────────────────────────────────
def _multi() -> Problem:
    return Problem(
        level=2,
        type="multi",
        question="교체 전략의 예시에 해당하는 것을 모두 고르시오",
        options=["FIFO", "OPT", "요구 반입", "최초 적합"],
        answer=["FIFO", "OPT"],
        explanation="원문에 교체 전략 예시로 나열됨",
        source_evidence="ex. FIFO, OPT, LRU, LFU, NUR",
    )


def _order() -> Problem:
    return Problem(
        level=3,
        type="order",
        question="기억장치 관리 전략의 결정 순서를 배열하시오",
        options=["반입", "배치", "교체"],
        answer=["반입", "배치", "교체"],
        explanation="언제→어디에→무엇을 교체",
        source_evidence="ex. FIFO, OPT, LRU, LFU, NUR",
    )


def test_multi_set_match_passes():
    # 순서가 달라도 구성이 같으면 통과해야 한다(multi는 집합 비교).
    passed, _ = _run(
        {"items": [{"id": 0, "answer": ["OPT", "FIFO"], "also_correct": []}]},
        [_multi()],
    )
    assert len(passed) == 1


def test_multi_missing_item_rejected():
    passed, reasons = _run(
        {"items": [{"id": 0, "answer": ["FIFO"], "also_correct": []}]}, [_multi()]
    )
    assert passed == [] and "다른 답" in reasons[0]


def test_multi_extra_correct_rejected():
    # 검수가 추가 정답을 지목 → 정답 비유일.
    passed, reasons = _run(
        {"items": [{"id": 0, "answer": ["FIFO", "OPT"], "also_correct": ["요구 반입"]}]},
        [_multi()],
    )
    assert passed == [] and "비유일" in reasons[0]


def test_order_sequence_must_match():
    # 순서가 다르면 폐기(order는 순서까지 본다).
    passed, reasons = _run(
        {"items": [{"id": 0, "answer": ["배치", "반입", "교체"], "also_correct": []}]},
        [_order()],
    )
    assert passed == [] and "다른 답" in reasons[0]


def test_order_alternative_ordering_rejected():
    # "다른 순서로도 성립"은 곧 정답 비유일이다.
    passed, reasons = _run(
        {
            "items": [
                {
                    "id": 0,
                    "answer": ["반입", "배치", "교체"],
                    "also_correct": [["배치", "반입", "교체"]],
                }
            ]
        },
        [_order()],
    )
    assert passed == [] and "비유일" in reasons[0]


def test_order_exact_sequence_passes():
    passed, _ = _run(
        {"items": [{"id": 0, "answer": ["반입", "배치", "교체"], "also_correct": []}]},
        [_order()],
    )
    assert len(passed) == 1


def test_prompt_shows_answer_format_per_type():
    # 유형마다 답 형식을 알려줘야 검수가 배열/문자열을 맞춰 준다.
    prompt = solve_check.build_prompt([_problem(), _multi(), _order()], SOURCE)
    assert "(mcq)" in prompt and "(multi)" in prompt and "(order)" in prompt
    assert "배열" in prompt


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
