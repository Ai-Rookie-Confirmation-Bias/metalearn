from app.features.quiz.planning import classify_form, plan_document
from app.features.quiz.schemas import FORM_TYPE_CANDIDATES, QuizGenConfig
from app.features.quiz.selection import select_chunk


def _plan(parsed_doc, config=None):
    selections = {c.index: select_chunk(c) for c in parsed_doc.chunks}
    return plan_document(parsed_doc, selections, config or QuizGenConfig())


def test_classify_form():
    assert classify_form("", "계획 수립 → 위험 분석 → 개발 및 검증 → 고객 평가") == "sequence"
    assert classify_form("5가지 핵심 가치", "용기, 단순성, 의사소통, 피드백, 존중") == "enumeration"
    assert classify_form("하향식과 달리 최하위 모듈부터", "상향식 설계") == "contrast"
    assert classify_form("조정자와 전문가 의견을 종합하는 기법", "델파이 기법이다") == "definition"


def test_classify_form_does_not_overfire_sequence():
    """QUIZ_TUNING §5-① 오분류 회귀: '단계' 키워드만으로 sequence가 되면 안 된다."""
    assert (
        classify_form(
            "LOC 기법을 보완하는 방법으로 생명 주기 각 단계별로 소요되는 인월 수를 산정",
            "개발 단계별 인월 수 (Effort Per Task) : LOC 기법 보완",
        )
        != "sequence"
    )
    # 화살표 1개는 절차 나열이 아님 (인과 표시 등)
    assert classify_form("", "델파이 기법 → 전문가 감정 기법의 편견 보완") != "sequence"


def test_every_planned_type_is_a_form_candidate(parsed_doc):
    for order in _plan(parsed_doc):
        for plan in order.concept_plans:
            for t in plan.types:
                assert t in FORM_TYPE_CANDIDATES[plan.form]


def test_coverage_floor_every_concept_gets_at_least_one(parsed_doc):
    """예산 바닥: 출제 가능 개념은 최소 1문항 계획돼야 한다 (docs/QUIZ.md §2-④)."""
    orders = _plan(parsed_doc)
    planned = {p.name for o in orders for p in o.concept_plans if p.types}
    selections = {c.index: select_chunk(c) for c in parsed_doc.chunks}
    eligible = {ec.concept.name for s in selections.values() for ec in s.eligible}
    assert eligible == planned


def test_toc_budget_clamp(parsed_doc):
    config = QuizGenConfig(toc_max=20, overgen_ratio=1.0)
    orders = _plan(parsed_doc, config)
    per_toc: dict[int, int] = {}
    for o in orders:
        per_toc[o.toc_index] = per_toc.get(o.toc_index, 0) + sum(
            len(p.types) for p in o.concept_plans
        )
    for total in per_toc.values():
        assert total <= 20


def test_per_concept_max_respected(parsed_doc):
    config = QuizGenConfig(toc_max=500, per_concept_max=2, overgen_ratio=1.0)
    for order in _plan(parsed_doc, config):
        for plan in order.concept_plans:
            assert len(plan.types) <= 2


def test_exam_frequency_boosts_allocation(parsed_doc):
    """기출 빈도가 높은 개념이 낮은 개념보다 문항을 더 받아야 한다."""
    selections = {c.index: select_chunk(c) for c in parsed_doc.chunks}
    target = selections[0].eligible[0].concept.name
    config = QuizGenConfig(toc_max=30, overgen_ratio=1.0)
    orders = plan_document(parsed_doc, selections, config, exam_frequency={target: 5})
    counts = {
        p.name: len(p.types) for o in orders for p in o.concept_plans
    }
    assert counts[target] == max(counts.values())


def test_classify_form_multi_bullets_not_sequence():
    """불릿 여러 줄(줄마다 화살표 1개)을 이어붙여 절차형으로 오판하지 않는다 —
    'UML 구성요소'가 cloze로 출제되던 실측 원인."""
    from app.features.quiz.planning import classify_form_multi

    lines = [
        "■ UML (Unified Modeling Language) → 구성요소 : 사물, 관계, 다이어그램",
        "■ 사물 → 모델을 구성하는 기본 요소",
    ]
    assert classify_form_multi("모델링 언어", lines) != "sequence"
    # 진짜 절차(한 문장 안 화살표 2개 이상)는 그대로 절차형
    assert classify_form_multi("", ["계획 수립 → 위험 분석 → 개발 및 검증"]) == "sequence"


def test_classify_form_table_text_is_enumeration():
    """표 블록이 문장 하나로 앵커링된 실데이터 — 셀 안 화살표로 절차형이 되면 안 된다."""
    from app.features.quiz.planning import classify_form

    table = "| 폭포수 | 선형 순차적 개발 → 고전적 모형 |\n| --- | --- |\n| 프로토타입 | 고객 요구 → 시제품 |"
    assert classify_form("", table) == "enumeration"
