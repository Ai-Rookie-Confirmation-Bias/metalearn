from app.features.quiz.grading import answer_payload, chosen_explanation, grade
from app.features.quiz.serving import strip_answers

MCQ = {
    "question": "q",
    "options": ["a", "b", "c", "d"],
    "answerIndex": 3,
    "explanation": "정답 해설",
    "wrongExplanations": {"0": "a라서 아님", "1": "b라서 아님", "2": "c라서 아님"},
}
CLOZE = {
    "segments": [
        {"kind": "text", "text": "계획 → "},
        {"kind": "blank", "answer": "위험 분석", "aliases": ["위험분석"]},
        {"kind": "text", "text": " → 개발"},
    ]
}
SHORT = {"prompt": "p", "accepted": ["델파이 기법", "델파이"], "explanation": "e"}
TF = {"statement": "s", "answer": False, "explanation": "e"}


def test_grade_mcq():
    assert grade("mcq", MCQ, 3)
    assert grade("mcq", MCQ, "3")
    assert not grade("mcq", MCQ, 0)
    assert not grade("mcq", MCQ, "abc")


def test_grade_cloze_with_alias_and_spacing():
    assert grade("cloze", CLOZE, ["위험 분석"])
    assert grade("cloze", CLOZE, ["위험분석"])
    assert grade("cloze", CLOZE, "위험분석")  # 빈칸 1개면 단일값 허용
    assert not grade("cloze", CLOZE, ["개발"])


def test_grade_short_answer_normalized():
    assert grade("shortAnswer", SHORT, "델파이  기법")
    assert grade("shortAnswer", SHORT, "델파이")
    assert not grade("shortAnswer", SHORT, "LOC")


def test_grade_true_false_accepts_korean_ox():
    assert grade("trueFalse", TF, False)
    assert grade("trueFalse", TF, "X")
    assert not grade("trueFalse", TF, "O")


def test_chosen_explanation_only_on_wrong_mcq():
    assert chosen_explanation("mcq", MCQ, 1, correct=False) == "b라서 아님"
    assert chosen_explanation("mcq", MCQ, 3, correct=True) is None
    assert chosen_explanation("trueFalse", TF, True, correct=False) is None


def test_strip_answers_leaks_nothing():
    """서빙 페이로드에 정답·해설 계열 키가 절대 없어야 한다 (치팅 방지)."""
    banned = {"answerindex", "answer", "accepted", "explanation", "wrongexplanations", "aliases"}

    def walk(node):
        if isinstance(node, dict):
            for k, v in node.items():
                assert k.lower() not in banned, k
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    for t, data in [("mcq", MCQ), ("cloze", CLOZE), ("shortAnswer", SHORT), ("trueFalse", TF)]:
        walk(strip_answers(t, data))

    # cloze 빈칸은 자리는 남되 정답은 없어야
    stripped = strip_answers("cloze", CLOZE)
    assert {"kind": "blank"} in stripped["segments"]


def test_answer_payload_shapes():
    assert answer_payload("mcq", MCQ)["answerIndex"] == 3
    assert answer_payload("cloze", CLOZE)["answers"][0]["answer"] == "위험 분석"
