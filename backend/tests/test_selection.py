from app.features.quiz.schemas import (
    ParsedChunk,
    ParsedConcept,
    ParsedFigure,
    SentenceAnchor,
)
from app.features.quiz.selection import select_chunk


def test_real_chunk_finds_evidence_for_most_concepts(parsed_doc):
    """실데이터 조각 #0: 개념 14개 대부분에 근거 문장이 잡혀야 한다."""
    sel = select_chunk(parsed_doc.chunks[0])
    assert len(sel.eligible) >= 10, sel.excluded_concepts
    for ec in sel.eligible:
        assert ec.evidence_sentence_ids


def test_greeting_sentences_are_not_evidence(parsed_doc):
    """조각 #0 앞부분(인사말·광고, 문장 0~16)은 어떤 개념의 근거도 아니어야 한다.

    개념 키워드 매칭 방식이라 인사말은 자연 탈락 — 이게 선별의 핵심 보증.
    """
    sel = select_chunk(parsed_doc.chunks[0])
    greeting_ids = set(range(17))
    for ec in sel.eligible:
        overlap = greeting_ids & set(ec.evidence_sentence_ids)
        # '기출'·'프로그래밍 언어' 같은 일반어 개념이 아닌 한 인사말에 걸리면 안 됨
        assert not overlap or ec.concept.name in {"LOC 기법"}, (
            ec.concept.name,
            overlap,
        )


def test_concept_without_evidence_is_excluded():
    chunk = ParsedChunk(
        index=0,
        page_from=1,
        page_to=1,
        raw_text="폭포수 모형은 고전적 개발 모형이다.",
        sentences=[SentenceAnchor(start=0, end=19)],
        concepts=[
            ParsedConcept(name="폭포수 모형", definition="고전적 모형"),
            ParsedConcept(name="양자 컴퓨팅", definition="원문에 없는 개념"),
        ],
    )
    sel = select_chunk(chunk)
    assert [ec.concept.name for ec in sel.eligible] == ["폭포수 모형"]
    assert "양자 컴퓨팅" in sel.excluded_concepts


def test_vision_dependent_sentences_are_banned():
    # 문장 0(그림 의존)과 문장 1이 비전 제외 반경(120자) 밖에 있도록 구성
    s0 = "그림과 같이 폭포수 구조가 나뉜다" + "." * 150
    s1 = "폭포수 모형은 고전적 모형이다."
    text = s0 + " " + s1
    chunk = ParsedChunk(
        index=0,
        page_from=1,
        page_to=1,
        raw_text=text,
        sentences=[
            SentenceAnchor(start=0, end=len(s0)),
            SentenceAnchor(start=len(s0) + 1, end=len(text)),
        ],
        concepts=[ParsedConcept(name="폭포수 모형", definition="")],
        figures=[ParsedFigure(page=1, offset=3, kind="figure", needs_vision=True)],
    )
    sel = select_chunk(chunk)
    # 근거는 두 번째 문장만 — 그림 의존 문장(0)은 제외
    assert sel.eligible[0].evidence_sentence_ids == [1]


def test_ocr_spacing_is_tolerated():
    """pilgi.pdf처럼 띄어쓰기가 붙은 OCR 원문에서도 매칭돼야 한다."""
    text = "•폭포수모형은이전단계로돌아갈수없다"
    chunk = ParsedChunk(
        index=0,
        page_from=1,
        page_to=1,
        raw_text=text,
        sentences=[SentenceAnchor(start=0, end=len(text))],
        concepts=[ParsedConcept(name="폭포수 모형", definition="")],
    )
    sel = select_chunk(chunk)
    assert sel.eligible
