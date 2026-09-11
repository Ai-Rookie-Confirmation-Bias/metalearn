from app.features.quiz.generation import (
    evidence_scope_reason,
    mechanical_check,
    parse_generation_response,
    parse_verification_response,
    resolve_evidence,
)
from app.features.quiz.schemas import (
    ChunkWorkOrder,
    ConceptPlan,
    GeneratedItem,
    ParsedChunk,
    SentenceAnchor,
)

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


def test_parse_generation_rescues_evidence_nested_in_data():
    """pro3 편차: evidence를 data 안에 넣음 — '근거 문장 번호 없음' 억울 폐기 구제."""
    raw = '{"items":[{"type":"trueFalse","concept":"폭포수",' \
          '"data":{"statement":"폭포수는 고전적 모형이다","answer":true,' \
          '"explanation":"","evidence":["s1"]},"difficulty":1}]}'
    items = parse_generation_response(raw)
    assert len(items) == 1
    assert items[0].evidence_sentence_ids == [1]
    assert "evidence" not in items[0].data  # data에서는 걷어냄


def test_parse_generation_drops_invalid_entries_individually():
    raw = '[{"type":"nope","concept":"x","data":{},"evidence":[]},' \
          '{"type":"trueFalse","concept":"y","data":{"statement":"s","answer":true},' \
          '"evidence":[0],"difficulty":1}]'
    items = parse_generation_response(raw)
    assert len(items) == 1
    assert items[0].concept == "y"


def test_mechanical_check_passes_good_mcq():
    assert mechanical_check(_item(), CHUNK) is None


def test_build_cloze_segments_assembles_from_pick():
    """cloze 재구성 ①: LLM 픽(문장·정답) → 코드가 지문 조립, 정답은 지문에서 제거."""
    from app.features.quiz.generation import build_cloze_segments

    item = _item(
        type="cloze",
        data={"sentence": "s0", "answer": "델파이 기법", "aliases": ["Delphi"]},
        evidence_sentence_ids=[0],
    )
    assert build_cloze_segments(item, CHUNK) is None
    kinds = [s["kind"] for s in item.data["segments"]]
    assert "blank" in kinds and "text" in kinds
    text = " ".join(s.get("text", "") for s in item.data["segments"] if s["kind"] == "text")
    assert "델파이 기법" not in text  # 정답 노출 원천 차단
    assert mechanical_check(item, CHUNK) is None  # 조립본이 기계 검사 통과


def test_build_cloze_segments_rejects_bad_picks():
    from app.features.quiz.generation import build_cloze_segments

    # 문장에 없는 정답
    missing = _item(type="cloze", data={"sentence": "s0", "answer": "없는 용어"},
                    evidence_sentence_ids=[0])
    assert "글자 그대로 없음" in build_cloze_segments(missing, CHUNK)
    # 구형 segments 응답은 그대로 통과 (기존 검사 경로)
    legacy = _item(type="cloze", data={"segments": [{"kind": "blank", "answer": "x"}]},
                   evidence_sentence_ids=[0])
    assert build_cloze_segments(legacy, CHUNK) is None
    assert "segments" in legacy.data


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


def test_mechanical_check_rejects_sentence_id_leak_in_explanation():
    """QUIZ_TUNING §7: 해설에 내부 문장 번호(s27)가 노출되면 폐기. 한글 뒤에서도 잡혀야 한다."""
    bad = _item()
    bad.data["explanation"] = "s27에 따라 델파이 기법은 의견을 종합한다."
    assert "문장 번호" in mechanical_check(bad, CHUNK)

    bad = _item()
    bad.data["wrongExplanations"]["1"] = "LOC 기법은 s3, s4의 설명이다."
    assert "문장 번호" in mechanical_check(bad, CHUNK)


def test_mechanical_check_sentence_ref_ignores_normal_words():
    """bus, os 같은 s+숫자 아닌 표기·영단어 내부의 s는 오탐하면 안 된다."""
    ok = _item()
    ok.data["explanation"] = "OS와 DBMS, windows10 환경에서도 동작한다."
    assert mechanical_check(ok, CHUNK) is None


def test_mechanical_check_rejects_polite_endings():
    """10회차 실측: "예측합니다"류 경어체를 심판 둘 다 놓침 — 기계 검사로 차단."""
    bad = _item()
    bad.data["question"] = "델파이 기법으로 무엇을 예측합니다?"
    assert "경어체" in mechanical_check(bad, CHUNK)

    bad = _item(
        type="cloze",
        data={"segments": [
            {"kind": "text", "text": "의견을 종합해 결과를 "},
            {"kind": "blank", "answer": "조정자"},
            {"kind": "text", "text": "가 예측해요."},
        ]},
    )
    assert "경어체" in mechanical_check(bad, CHUNK)


def test_mechanical_check_polite_endings_no_false_positives():
    """시험 문체("~쓰시오", "~아니다")와 '니다'로 끝나는 일반 표현은 오탐하면 안 된다."""
    ok = _item(
        type="shortAnswer",
        data={"prompt": "조정자와 전문가 의견을 종합하는 기법을 쓰시오.", "accepted": ["델파이 기법"]},
    )
    assert mechanical_check(ok, CHUNK) is None

    ok = _item(type="trueFalse", data={"statement": "폭포수 모형은 반복적 모형이 아니다.", "answer": False, "explanation": "고전적 선형 모형이다."})
    assert mechanical_check(ok, CHUNK) is None


def _order(**overrides) -> ChunkWorkOrder:
    base = dict(
        toc_index=0,
        chunk_index=3,
        concept_plans=[
            ConceptPlan(name="델파이 기법", definition="전문가 의견 종합", form="definition",
                        types=["mcq"], evidence_sentence_ids=[0]),
            ConceptPlan(name="폭포수 모형", definition="고전적 모형", form="definition",
                        types=["trueFalse"], evidence_sentence_ids=[1]),
        ],
    )
    base.update(overrides)
    return ChunkWorkOrder.model_validate(base)


def test_evidence_scope_within_plan_passes():
    assert evidence_scope_reason(_item(evidence_sentence_ids=[0]), _order()) is None


def test_evidence_scope_outside_plan_is_rejected():
    """QUIZ_TUNING §9-①: 다른 개념의 문장을 근거로 잡으면(근거 오매칭) 차단.

    심판·풀이자는 '주어진 근거'를 전제로 판정하므로 여기서 못 막으면 끝까지 못 잡는다.
    """
    reason = evidence_scope_reason(_item(evidence_sentence_ids=[0, 1]), _order())
    assert reason is not None and "선별된 후보 밖" in reason


def test_evidence_scope_unknown_concept_falls_back_to_union():
    """LLM이 개념 이름을 변형해도(계획에 없음) 조각 내 후보 합집합까지는 허용."""
    item = _item(concept="델파이", evidence_sentence_ids=[1])
    assert evidence_scope_reason(item, _order()) is None
    item = _item(concept="델파이", evidence_sentence_ids=[2])
    assert "선별된 후보 밖" in evidence_scope_reason(item, _order())


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

# ── 개조식·나열 게이트 + 인정 표기 보강 (세션 12) ──────────────

LIST_CHUNK = ParsedChunk(
    index=4,
    page_from=5,
    page_to=5,
    raw_text="■ UML (Unified Modeling Language) → 구성요소 : 사물, 관계, 다이어그램. 절차는 계획 → 설계 → 구현 순서로 진행한다.",
    sentences=[SentenceAnchor(start=0, end=57), SentenceAnchor(start=58, end=84)],
)


def test_build_cloze_rejects_enumeration_slot():
    """쉼표 나열의 한 자리를 비우면 '남은 항목 찾기' 퍼즐 — UML 구성요소 실측."""
    from app.features.quiz.generation import build_cloze_segments

    first = _item(type="cloze", data={"sentence": "s0", "answer": "사물"},
                  evidence_sentence_ids=[0])
    assert "나열" in build_cloze_segments(first, LIST_CHUNK)
    middle = _item(type="cloze", data={"sentence": "s0", "answer": "관계"},
                   evidence_sentence_ids=[0])
    assert "나열" in build_cloze_segments(middle, LIST_CHUNK)


def test_build_cloze_strips_bullet_and_allows_sequence():
    """불릿 마커는 지문에서 제거하고, 절차 나열(→)의 빈칸은 순서가 유일성을 주므로 허용."""
    from app.features.quiz.generation import build_cloze_segments

    seq = _item(type="cloze", data={"sentence": "s1", "answer": "설계"},
                evidence_sentence_ids=[1])
    assert build_cloze_segments(seq, LIST_CHUNK) is None
    stem = "".join(s.get("text", "") for s in seq.data["segments"])
    assert "■" not in stem


def test_augment_notations_adds_paren_variants():
    """개념 이름의 괄호 병기로 한/영 인정 표기를 코드가 보강한다 (accepted 부실 실측)."""
    from app.features.quiz.generation import augment_notations

    chunk = ParsedChunk(
        index=5, page_from=1, page_to=1,
        raw_text="팬아웃은 모듈이 호출하는 하위 모듈 수다.",
        sentences=[SentenceAnchor(start=0, end=22)],
        concepts=[{"name": "팬아웃(Fan-out)", "definition": "호출하는 하위 모듈 수"}],
    )
    item = _item(
        type="shortAnswer", concept="팬아웃",
        data={"prompt": "모듈이 호출하는 하위 모듈 수는?", "accepted": ["팬아웃"],
              "explanation": ""},
        evidence_sentence_ids=[0],
    )
    augment_notations(item, chunk)
    assert "Fan-out" in item.data["accepted"]

    other = _item(
        type="shortAnswer", concept="응집도",
        data={"prompt": "...", "accepted": ["응집도"], "explanation": ""},
        evidence_sentence_ids=[0],
    )
    augment_notations(other, chunk)
    assert other.data["accepted"] == ["응집도"]  # 무관한 병기는 안 붙는다


def test_build_cloze_rejects_table_text():
    """표 블록 앵커 위에 빈칸을 뚫으면 지문이 표 파이프 그대로 나온다 — 조립에서 차단."""
    from app.features.quiz.generation import build_cloze_segments

    raw = "| 폭포수 | 선형 순차적 개발 모형이다 |"
    chunk = ParsedChunk(
        index=6, page_from=1, page_to=1, raw_text=raw,
        sentences=[SentenceAnchor(start=0, end=len(raw))],
    )
    item = _item(type="cloze", data={"sentence": "s0", "answer": "폭포수"},
                 evidence_sentence_ids=[0])
    assert "표 텍스트" in build_cloze_segments(item, chunk)
