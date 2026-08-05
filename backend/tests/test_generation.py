from app.features.quiz.generation import (
    mechanical_check,
    parse_generation_response,
    parse_verification_response,
    resolve_evidence,
)
from app.features.quiz.schemas import GeneratedItem, ParsedChunk, SentenceAnchor

CHUNK = ParsedChunk(
    index=3,
    page_from=5,
    page_to=6,
    raw_text="델파이 기법은 조정자와 전문가 의견을 종합한다. 폭포수 모형은 고전적 모형이다.",
    sentences=[SentenceAnchor(start=0, end=26), SentenceAnchor(start=27, end=44)],
)


def _item(**overrides) -> GeneratedItem:
    base = dict(
        type="mcq",
        concept="델파이 기법",
        data={
            "question": "조정자와 전문가 의견을 종합하는 기법은?",
            "options": ["델파이 기법", "LOC 기법", "전문가 감정", "폭포수"],
            "answerIndex": 0,
            "explanation": "...",
            "wrongExplanations": {"1": "...", "2": "...", "3": "..."},
        },
        evidence_sentence_ids=[0],
        difficulty=2,
    )
    base.update(overrides)
    return GeneratedItem.model_validate(base)


def test_parse_generation_with_fence_and_chatter():
    raw = '생성했습니다!\n```json\n[{"type":"trueFalse","concept":"폭포수",' \
          '"data":{"statement":"폭포수는 고전적 모형이다","answer":true,"explanation":""},' \
          '"evidence":["s1"],"difficulty":1}]\n```'
    items = parse_generation_response(raw)
    assert len(items) == 1
    assert items[0].evidence_sentence_ids == [1]


def test_parse_generation_drops_invalid_entries_individually():
    raw = '[{"type":"nope","concept":"x","data":{},"evidence":[]},' \
          '{"type":"trueFalse","concept":"y","data":{"statement":"s","answer":true},' \
          '"evidence":[0],"difficulty":1}]'
    items = parse_generation_response(raw)
    assert len(items) == 1
    assert items[0].concept == "y"


def test_mechanical_check_passes_good_mcq():
    assert mechanical_check(_item(), CHUNK) is None


def test_mechanical_check_rejects_missing_evidence():
    assert mechanical_check(_item(evidence_sentence_ids=[]), CHUNK) == "근거 문장 번호 없음"


def test_mechanical_check_rejects_unknown_sentence_id():
    assert "존재하지 않는" in mechanical_check(_item(evidence_sentence_ids=[9]), CHUNK)


def test_mechanical_check_rejects_bad_answer_index():
    bad = _item()
    bad.data["answerIndex"] = 7
    assert "answerIndex" in mechanical_check(bad, CHUNK)


def test_mechanical_check_rejects_mcq_without_exactly_4_options():
    bad = _item()
    bad.data["options"] = ["델파이 기법", "LOC 기법", "전문가 감정", "폭포수", "나선형"]
    assert "4개가 아님" in mechanical_check(bad, CHUNK)


def test_mechanical_check_rejects_cloze_answer_leaked_in_text():
    """QUIZ_TUNING §5-②: 빈칸 정답이 지문에 그대로 보이면 문항이 무의미."""
    item = _item(
        type="cloze",
        data={"segments": [
            {"kind": "text", "text": "델파이 기법은 조정자와 전문가 의견을 종합한다. 이때 "},
            {"kind": "blank", "answer": "조정자"},
            {"kind": "text", "text": "가 의견을 모은다."},
        ]},
        evidence_sentence_ids=[0],
    )
    assert "지문에 노출" in mechanical_check(item, CHUNK)


def test_mechanical_check_strips_alias_equal_to_answer():
    item = _item(
        type="cloze",
        data={"segments": [
            {"kind": "text", "text": "의견을 종합하는 사람은 "},
            {"kind": "blank", "answer": "조정자", "aliases": ["조정자", "coordinator"]},
        ]},
        evidence_sentence_ids=[0],
    )
    assert mechanical_check(item, CHUNK) is None
    assert item.data["segments"][1]["aliases"] == ["coordinator"]


def test_mechanical_check_cloze_answer_must_be_in_evidence():
    item = _item(
        type="cloze",
        data={"segments": [
            {"kind": "text", "text": "델파이 기법은 "},
            {"kind": "blank", "answer": "양자컴퓨터"},
        ]},
        evidence_sentence_ids=[0],
    )
    assert "근거 문장에 없음" in mechanical_check(item, CHUNK)

    item.data["segments"][1]["answer"] = "조정자"
    assert mechanical_check(item, CHUNK) is None


def test_verification_parse_is_conservative_on_garbage():
    verdicts = parse_verification_response("판정 불가", 2)
    assert verdicts == [(False, "심판 응답 파싱 실패")] * 2


def test_verification_parse_normal():
    raw = '[{"index":0,"pass":true,"reason":""},{"index":1,"pass":false,"reason":"정답 2개"}]'
    assert parse_verification_response(raw, 2) == [(True, ""), (False, "정답 2개")]


def test_resolve_evidence_slices_source_text():
    ev = resolve_evidence(_item(evidence_sentence_ids=[0]), CHUNK)
    assert ev["chunkIndex"] == 3
    assert ev["sentenceRanges"] == [[0, 26]]
    assert ev["text"] == "델파이 기법은 조정자와 전문가 의견을 종합한다."
    assert ev["pageFrom"] == 5
