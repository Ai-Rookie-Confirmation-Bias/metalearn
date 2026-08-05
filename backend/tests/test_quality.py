"""core/quality — 공통 검증기 단위 테스트 (기능 소속 없음)."""
from app.core.llm.base import LLMClient
from app.core.quality import CandidateItem, QualityConfig, validate_items
from app.core.quality.checks import check_solution, polish_mcq

MCQ_DATA = {
    "question": "조정자와 전문가 의견을 종합하는 기법은?",
    "options": ["델파이 기법", "LOC 기법", "전문가 감정 기법", "폭포수 모형"],
    "answerIndex": 0,
    "explanation": "e",
    "wrongExplanations": {"1": "LOC라서 아님", "2": "감정이라서 아님", "3": "모형이라서 아님"},
}


# ── polish_mcq: 오답 과생성 후 선별 ──────────────────────


def test_polish_mcq_without_pool_is_noop():
    data = dict(MCQ_DATA)
    polish_mcq(data)
    assert data["options"] == MCQ_DATA["options"]
    assert data["answerIndex"] == 0


def test_polish_mcq_selects_from_pool_and_keeps_answer():
    data = {
        **MCQ_DATA,
        "options": ["델파이 기법", "LOC", "아주아주아주아주아주 길어서 티가 나는 오답 선지", "폭포수 모형"],
        "distractorPool": [
            {"text": "전문가 감정 기법", "why": "주관적 편견 보완 전"},
            {"text": "나선형 모형", "why": "개발 모형임"},
        ],
    }
    polish_mcq(data)
    opts = data["options"]
    assert len(opts) == 4
    assert opts[data["answerIndex"]] == "델파이 기법"
    # 길이 이질성이 큰 오답은 풀의 후보로 대체됨
    assert "아주아주아주아주아주 길어서 티가 나는 오답 선지" not in opts
    assert "distractorPool" not in data  # 저장 전 제거
    # 풀에서 온 후보(정답과 길이 동질)가 선지로 승격되고 why도 승계됨
    idx = opts.index("나선형 모형")
    assert data["wrongExplanations"][str(idx)] == "개발 모형임"


def test_polish_mcq_is_deterministic():
    d1 = {**MCQ_DATA, "distractorPool": [{"text": "나선형 모형", "why": "w"}]}
    d2 = {**MCQ_DATA, "distractorPool": [{"text": "나선형 모형", "why": "w"}]}
    polish_mcq(d1)
    polish_mcq(d2)
    assert d1["options"] == d2["options"]
    assert d1["answerIndex"] == d2["answerIndex"]


# ── check_solution: 풀이 왕복 판정 ───────────────────────


def test_check_solution_mcq():
    assert check_solution("mcq", MCQ_DATA, [0]) is None
    assert "다른 답" in check_solution("mcq", MCQ_DATA, [2])
    assert "복수 정답" in check_solution("mcq", MCQ_DATA, [0, 2])
    assert check_solution("mcq", MCQ_DATA, None) == "풀이자 응답 없음"


def test_check_solution_other_types_use_grader():
    short = {"prompt": "p", "accepted": ["델파이 기법", "델파이"]}
    assert check_solution("shortAnswer", short, "델파이") is None
    assert "불일치" in check_solution("shortAnswer", short, "폭포수")
    tf = {"statement": "s", "answer": True}
    assert check_solution("trueFalse", tf, True) is None


# ── validate_items: 단계 흐름 ────────────────────────────


class ScriptedLLM(LLMClient):
    """심판 전원 합격 / 풀이자는 지정된 답 / 수정은 지정된 응답."""

    def __init__(self, solver_answer="true", revision="[]"):
        self.solver_answer = solver_answer
        self.revision = revision
        self.calls: list[str] = []

    async def generate(self, prompt: str, **kwargs: object) -> str:
        if "출제 검수자" in prompt:
            self.calls.append("judge")
            n = prompt.count("[문항 ")
            return "[" + ",".join(f'{{"index":{i},"pass":true,"reason":""}}' for i in range(n)) + "]"
        if "너는 수험생이다" in prompt:
            self.calls.append("solve")
            n = prompt.count("[문항 ")
            return "[" + ",".join(f'{{"index":{i},"answer":{self.solver_answer}}}' for i in range(n)) + "]"
        if "검수 불합격" in prompt:
            self.calls.append("revise")
            return self.revision
        return "[]"

    async def embed(self, text: str) -> list[float]:
        return []


def _tf_item(statement="폭포수 모형은 고전적 모형이다") -> CandidateItem:
    return CandidateItem(
        type="trueFalse",
        data={"statement": statement, "answer": True, "explanation": "e"},
        evidence_text="폭포수 모형은 고전적 모형이다.",
    )


async def test_validator_full_pass():
    verdicts = await validate_items([_tf_item()], ScriptedLLM())
    assert verdicts[0].ok and not verdicts[0].revised


async def test_validator_solve_failure_then_revision_gives_up():
    # 풀이자가 오답(false) → solve 탈락 → 수정 응답 없음 → 최종 불합격
    llm = ScriptedLLM(solver_answer="false")
    verdicts = await validate_items([_tf_item()], llm)
    assert not verdicts[0].ok
    assert verdicts[0].stage == "solve"
    assert "revise" in llm.calls  # 수정 시도는 했다


async def test_validator_solve_disabled_by_config():
    llm = ScriptedLLM(solver_answer="false")
    config = QualityConfig(enable_solve=False, enable_revise=False)
    verdicts = await validate_items([_tf_item()], llm, config)
    assert verdicts[0].ok
    assert "solve" not in llm.calls


async def test_validator_skips_solve_for_unknown_types():
    """explainBack처럼 정답 키가 없는 유형은 풀이 왕복을 건너뛴다 (기계+심판만)."""
    item = CandidateItem(
        type="explainBack",
        data={"prompt": "설명해보라", "rubric": ["핵심1"]},
        evidence_text="근거",
    )
    llm = ScriptedLLM(solver_answer="false")  # 풀리면 무조건 탈락일 답
    verdicts = await validate_items([item], llm)
    assert verdicts[0].ok  # solve 미적용이라 통과


async def test_validator_mechanical_failure_revived_by_revision():
    bad = CandidateItem(
        type="trueFalse",
        data={"statement": "", "answer": True},  # statement 누락 → mechanical 탈락
        evidence_text="폭포수 모형은 고전적 모형이다.",
    )
    revision = '[{"index":0,"data":{"statement":"폭포수 모형은 고전적 모형이다","answer":true}}]'
    verdicts = await validate_items([bad], ScriptedLLM(revision=revision))
    assert verdicts[0].ok
    assert verdicts[0].revised
    assert verdicts[0].item.data["statement"]
