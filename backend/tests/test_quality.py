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


def test_check_solution_unwraps_single_element_list():
    """풀이자가 답을 ["로킹 단위"]처럼 배열로 감싸는 형식 편차 — 내용이 맞으면 통과.

    10회차 실측에서 정답인데 형식 때문에 폐기된 문항 다수 (억울한 폐기).
    """
    short = {"prompt": "p", "accepted": ["로킹 단위"]}
    assert check_solution("shortAnswer", short, ["로킹 단위"]) is None
    assert "불일치" in check_solution("shortAnswer", short, ["폭포수"])  # 오답은 여전히 탈락
    assert "불일치" in check_solution("shortAnswer", short, ["로킹 단위", "잠금"])  # 복수 답은 그대로
    tf = {"statement": "s", "answer": True}
    assert check_solution("trueFalse", tf, [True]) is None
    # mcq는 복수 원소가 '복수 정답 판단' 신호라 unwrap 안 함 — 기존 의미 유지
    assert check_solution("mcq", MCQ_DATA, [0]) is None


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


async def test_validator_cross_model_split():
    """교차 검증: 심판·풀이는 verify 모델, 수정은 revise 모델이 맡는다."""
    verify = ScriptedLLM(solver_answer="false")  # 풀이 탈락 유도 → 수정 루프 진입
    revise = ScriptedLLM()
    await validate_items([_tf_item()], verify, revise_llm=revise)
    assert "judge" in verify.calls and "solve" in verify.calls
    assert verify.calls.count("revise") == 0
    assert revise.calls == ["revise"]  # 수정 콜만 revise 모델로


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


def test_extract_json_salvages_truncated_array():
    """토큰 한도로 잘린 심판 배열 — 완결된 객체만 건진다 (K-EXAONE 실측 패턴)."""
    from app.core.quality.parsing import parse_verdicts

    raw = '[{"index":0,"pass":true,"reason":""},{"index":1,"pass":false,"reason":"근거 \\"불일치\\""},{"index":2,"pass":fal'
    verdicts = parse_verdicts(raw, 3)
    assert verdicts[0] == (True, "")
    assert verdicts[1] == (False, '근거 "불일치"')
    assert verdicts[2] is None  # 잘린 객체 = 판독 불가 (해석은 validator 몫)


def test_extract_json_concatenated_objects():
    """객체 이어붙임 `{...}{...}` — solar-pro3 실측 형태. 전부 건져 배열로."""
    from app.core.quality.parsing import extract_json

    raw = '{"index":0,"pass":true,"reason":""}\n{"index":1,"pass":false,"reason":"모호"}'
    assert extract_json(raw) == [
        {"index": 0, "pass": True, "reason": ""},
        {"index": 1, "pass": False, "reason": "모호"},
    ]


def test_extract_json_single_object_with_trailing_prose():
    """단일 객체 뒤 잡담(중괄호 포함)은 이어붙임이 아니다 — 객체 그대로."""
    from app.core.quality.parsing import extract_json

    raw = '{"a":1} 참고: {중괄호가 든 설명}'
    assert extract_json(raw) == {"a": 1}


def test_check_solution_normalizes_string_bool_and_option_text():
    """pro3 풀이자 형식 편차 — 'False' 문자열, 선지 텍스트 답변을 내용 기준으로 판정."""
    from app.core.quality.checks import check_solution

    tf = {"statement": "s", "answer": False}
    assert check_solution("trueFalse", tf, "False") is None
    assert check_solution("trueFalse", tf, "true") is not None  # 오답은 여전히 불합격

    mcq = {"question": "q", "options": ["COMMIT", "ROLLBACK", "START", "REDO"], "answerIndex": 3}
    assert check_solution("mcq", mcq, "REDO") is None
    assert check_solution("mcq", mcq, "COMMIT") is not None  # 다른 선지 = 오답
    assert check_solution("mcq", mcq, "없는 선지") is not None  # 일치 없음 = 형식 불량


def test_parse_solutions_accepts_bare_object():
    """문항 1개 배치에 배열 없이 답하는 경우(pro3 실측) — 1원소 배열로 취급."""
    from app.core.quality.parsing import parse_solutions, parse_verdicts

    assert parse_solutions('{"index":0,"answer":"델파이 기법"}', 1) == ["델파이 기법"]
    assert parse_verdicts('{"index":0,"pass":true,"reason":""}', 1) == [(True, "")]


def test_extract_list_unwraps_wrapper_objects():
    """json_object 강제 시 래퍼 계약 — {"items"/"verdicts"/"answers"/"revisions":[...]}."""
    from app.core.quality.parsing import extract_list

    assert extract_list('{"verdicts":[{"index":0,"pass":true}]}') == [{"index": 0, "pass": True}]
    assert extract_list('{"answers":[{"index":0,"answer":[2]}]}') == [{"index": 0, "answer": [2]}]
    # 래퍼 키가 아니어도 리스트 값이 유일하면 그걸 취한다 (키 이름 변형 대비)
    assert extract_list('{"results":[{"index":0}]}') == [{"index": 0}]
    # 배열 그대로 답하는 모델(EXAONE)도 그대로 통과
    assert extract_list('[{"index":0}]') == [{"index": 0}]


def test_scrub_sentence_refs_removes_citations():
    """pro3의 sN 인용을 코드로 제거 — 폐기 대신 전처리로 살린다 (§12)."""
    from app.core.quality.checks import mechanical_check, scrub_sentence_refs

    d = {
        "statement": "s31에 따르면 반정규화는 정규화 원칙을 위반한다.",
        "answer": True,
        "explanation": "반정규화는 의도적 중복 허용이다 (s31).",
    }
    scrub_sentence_refs("trueFalse", d)
    assert d["statement"] == "반정규화는 정규화 원칙을 위반한다."
    assert d["explanation"] == "반정규화는 의도적 중복 허용이다."
    assert mechanical_check("trueFalse", d, "반정규화 근거") is None

    # 패턴 밖 변형은 못 지워도 검사가 잡는다 (조용히 통과 금지)
    d2 = {"statement": "정답은 s31 문장이 결정한다.", "answer": True, "explanation": ""}
    scrub_sentence_refs("trueFalse", d2)
    assert mechanical_check("trueFalse", d2, "근거") is not None


def test_mechanical_check_cloze_phrase_blank_limits():
    """§9-② — 빈칸 3개 이상·정답 15자 초과·화살표 포함 cloze 폐기."""
    from app.core.quality.checks import mechanical_check

    def cloze(*blanks):
        segs = [{"kind": "text", "text": "본문 "}]
        segs += [{"kind": "blank", "answer": a, "aliases": []} for a in blanks]
        return {"segments": segs}

    ev = "고객의 need 파악 위해 견본/시제품을 통해 최종 결과 예측 A B C D 계획→분석"
    assert "15자 초과" in mechanical_check(
        "cloze", cloze("고객의 need 파악 위해 견본/시제품을 통해 최종 결과 예측"), ev
    )
    assert "화살표" in mechanical_check("cloze", cloze("계획→분석"), ev)
    assert "2개 초과" in mechanical_check("cloze", cloze("A", "B", "C"), ev)
    assert mechanical_check("cloze", cloze("시제품"), ev) is None  # 낱말 빈칸은 통과


def test_check_solution_short_answer_colon_prefix():
    """단답에 '용어 : 정의'로 답하는 pro3 편차 — 콜론 앞 용어로 채점."""
    from app.core.quality.checks import check_solution

    data = {"prompt": "p", "accepted": ["COMMIT"]}
    assert check_solution("shortAnswer", data, "COMMIT : 트랜잭션 정상 종료 후 반영") is None
    assert check_solution("shortAnswer", data, "ROLLBACK : 취소") is not None


def test_check_solution_leniency_suffix_paren_and_cloze_string():
    """풀이 대조 완화 ②: 괄호 병기·접미 수식·cloze 문자열 답변을 내용 기준 판정."""
    from app.core.quality.checks import check_solution

    sa = {"prompt": "p", "accepted": ["개발 단계별 인월 수"]}
    assert check_solution("shortAnswer", sa, "개발 단계별 인월 수 (Effort Per Task)") is None
    assert check_solution("shortAnswer", sa, "개발 단계별 인월 수 산정 방법") is None
    assert check_solution("shortAnswer", sa, "LOC 기법") is not None

    mcq = {"question": "q", "options": ["a", "b", "c", "d"], "answerIndex": 2}
    assert check_solution("mcq", mcq, "2번") is None

    cloze = {"segments": [
        {"kind": "text", "text": "본문 "},
        {"kind": "blank", "answer": "델파이", "aliases": []},
    ]}
    assert check_solution("cloze", cloze, "델파이") is None  # 배열 없이 문자열


# ── 배심원단 (second_llm) ────────────────────────────────


class JuryLLM(ScriptedLLM):
    """배심원 역할 — 심판/풀이 응답을 시나리오로 지정."""

    def __init__(self, judge_raw=None, solver_answer="true"):
        super().__init__(solver_answer=solver_answer)
        self.judge_raw = judge_raw  # None이면 전원 합격

    async def generate(self, prompt: str, **kwargs: object) -> str:
        if "출제 검수자" in prompt and self.judge_raw is not None:
            self.calls.append("judge")
            return self.judge_raw
        return await super().generate(prompt, **kwargs)


async def test_jury_second_judge_failure_kills_item():
    """1차(Solar) 합격이어도 배심원이 잡으면 탈락."""
    jury = JuryLLM(judge_raw='[{"index":0,"pass":false,"reason":"정답 유일성 붕괴"}]')
    config = QualityConfig(enable_revise=False)
    verdicts = await validate_items([_tf_item()], ScriptedLLM(), config, second_llm=jury)
    assert not verdicts[0].ok
    assert verdicts[0].stage == "judge"
    assert "[배심]" in verdicts[0].reason


async def test_jury_garbage_judge_abstains():
    """배심원 응답이 판독 불가면 기권 — 1차 합격이 유지된다 (학살 방지)."""
    jury = JuryLLM(judge_raw="판정 형식이 아닌 잡담")
    config = QualityConfig(enable_revise=False)
    verdicts = await validate_items([_tf_item()], ScriptedLLM(), config, second_llm=jury)
    assert verdicts[0].ok


async def test_jury_second_solver_wrong_answer_kills():
    """배심원 풀이자가 다른 답을 내면 탈락 (두 학생 모두 풀 수 있어야 통과)."""
    jury = JuryLLM(solver_answer="false")
    config = QualityConfig(enable_revise=False)
    verdicts = await validate_items([_tf_item()], ScriptedLLM(), config, second_llm=jury)
    assert not verdicts[0].ok
    assert verdicts[0].stage == "solve"
    assert "[배심]" in verdicts[0].reason


async def test_jury_second_solver_missing_answer_abstains():
    """배심원 풀이자가 무응답이면 기권 (형식 난조 ≠ 문항 결함)."""
    jury = JuryLLM(solver_answer="null")
    config = QualityConfig(enable_revise=False)
    verdicts = await validate_items([_tf_item()], ScriptedLLM(), config, second_llm=jury)
    assert verdicts[0].ok


async def test_jury_neutral_example_used_for_second_judge():
    """배심원 심판 프롬프트에는 앵무새 유발 예시 문구가 없어야 한다."""
    from app.core.quality.prompts import build_judge_prompt

    prompt = build_judge_prompt([_tf_item()], neutral_example=True)
    assert "피드백" not in prompt
    assert "예시 문구를 복사하지 마라" in prompt
