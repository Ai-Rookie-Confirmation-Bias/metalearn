"""26·27 조달 — 순수 로직만. DB·LLM은 안 부른다.

여기서 지키는 것:
  ① 안다고 **확인된** 것만 숨긴다 — 안 물어본 과목을 건너뛰면 보강이 0이 된다
  ② 자료는 (분야, 과목) 소유 — 같은 쌍이면 같은 지문, 분야가 다르면 다른 지문
  ③ note가 판정 근거를 그대로 들고 있다
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.features.course.models import TopicPlan  # noqa: E402
from app.features.course.prompts import supply as supply_prompt  # noqa: E402
from app.features.course.search import HEARD, KNOWN, UNKNOWN  # noqa: E402
from app.features.course.supply import (  # noqa: E402
    HIT_PREFIX,
    _as_index,
    _fingerprint,
    _note_of,
    _plan_of,
    covered_by,
)


class Row:
    """CoursePrereq에서 판정에 쓰는 칸만."""

    def __init__(self, known=None, verified=None):
        self.known = known
        self.verified = verified


# ── ① 무엇을 숨기나 ──────────────────────────────────────────────


def test_전부_안다고_확인되면_숨긴다():
    rows = [Row(KNOWN), Row(KNOWN), Row(KNOWN)]
    assert _plan_of(rows) == TopicPlan.SKIP.value


def test_하나라도_모르면_낸다():
    rows = [Row(KNOWN), Row(UNKNOWN), Row(KNOWN)]
    assert _plan_of(rows) == TopicPlan.BRIEF.value


def test_진단을_안_했으면_낸다():
    """실측: AWS 코스가 known=NULL이라 6과목 전부 skip으로 깔렸다.

    선수는 정의상 코스 자료가 안 가르치는 것이다. 모르면 주는 쪽이 맞다.
    """
    assert _plan_of([Row(), Row(), Row()]) == TopicPlan.BRIEF.value
    assert _plan_of([Row(KNOWN), Row(), Row(KNOWN)]) == TopicPlan.BRIEF.value


def test_들어봤다가_남아_있어도_낸다():
    """24가 heard를 안 남기지만, 진단을 건너뛴 경로로 들어올 수 있다."""
    assert _plan_of([Row(KNOWN), Row(HEARD)]) == TopicPlan.BRIEF.value


def test_항목이_없으면_낸다():
    assert _plan_of([]) == TopicPlan.BRIEF.value


# ── ② 자료의 주인은 (분야, 과목) ────────────────────────────────


def test_같은_분야_같은_과목이면_같은_지문():
    assert _fingerprint("정보처리기사", "자료구조") == _fingerprint(
        "정보처리기사", "자료구조"
    )


def test_분야가_다르면_다른_자료다():
    """`정규화`가 DB에서는 중복 제거, 머신러닝에서는 값 범위 맞추기다."""
    assert _fingerprint("데이터베이스", "정규화") != _fingerprint(
        "머신러닝", "정규화"
    )
    assert _fingerprint("A", "B") != _fingerprint("B", "A")


def test_지문이_문서_지문과_같은_규격이다():
    assert len(_fingerprint("가", "나")) == 64


# ── ③ 근거를 남긴다 ─────────────────────────────────────────────


def test_note가_판정을_그대로_적는다():
    rows = [Row(KNOWN, True), Row(UNKNOWN, False), Row(KNOWN)]
    note = _note_of(rows, None)
    assert "3항목" in note and "안다 2" in note and "모른다 1" in note
    assert "확인 문항 2" in note
    assert "미확인" not in note


def test_안_물어본_항목을_따로_센다():
    note = _note_of([Row(KNOWN), Row(), Row()], None)
    assert "미확인 2" in note


def hit(filename: str, concept: str, similarity: float) -> dict:
    """`_existing_hits`가 돌려주는 모양. 확정 화면(⑥)이 구조를 그대로 쓴다."""
    return {
        "document_id": "d",
        "filename": filename,
        "concept": concept,
        "item": "아무 항목",
        "similarity": similarity,
    }


def test_대체_자료가_있으면_붙인다():
    note = _note_of([Row(KNOWN)], hit("pilgi.pdf", "자료 구조", 0.83))
    assert note.endswith("(0.83)")
    assert "pilgi.pdf" in note
    assert "진단:" in note


def test_대체_자료가_없으면_진단만_적는다():
    assert _note_of([Row(KNOWN)], None).startswith("진단:")


def test_note에서_책장_히트만_떼어낸다():
    """★ 만드는 쪽(`_note_of`)과 읽는 쪽(`covered_by`)이 같은 상수를 봐야 한다.

    `note`는 진단 통계와 히트가 한 줄에 붙어 있다. 앞부분은 왜 이 단원이
    생겼는지 적은 디버그 문장이라 학습자에게 보여줄 것이 아니고, 뒷부분만
    화면에 값이 있다 — "AI가 새로 썼습니다"와 "그 책 어디에 있습니다"는
    학습자에게 전혀 다른 말이다.

    접두사를 한쪽만 고치면 화면에서 **조용히 사라진다.** 그래서 잠근다.
    """
    note = _note_of(
        [Row(KNOWN), Row(UNKNOWN)], hit("운영체제_2장.pdf", "인터럽트", 0.82)
    )

    assert HIT_PREFIX in note
    assert covered_by(note) == "운영체제_2장.pdf — 인터럽트 (0.82)"
    assert "진단:" in note  # 통계는 note에 그대로 남는다

    # 히트가 없으면 화면도 조용하다 — 그때는 AI가 쓴 단원이다.
    assert covered_by(_note_of([Row(KNOWN)], None)) is None
    assert covered_by(None) is None
    assert covered_by("") is None


# ── ④ LLM 응답 방어 ─────────────────────────────────────────────


def test_LLM이_준_번호를_방어적으로_읽는다():
    assert _as_index(1, 3) == 1
    assert _as_index("2", 3) == 2
    assert _as_index(9, 3) is None
    assert _as_index(-1, 3) is None
    assert _as_index(None, 3) is None
    assert _as_index(True, 3) is None   # bool은 int의 하위형이다


def test_명세_프롬프트가_분야를_싣는다():
    """항목 이름만으로는 어느 분야의 개념인지 모른다."""
    text = supply_prompt.build_prompt(
        field="데이터베이스", subject="관계형 모델", items=["정규화", "키"]
    )
    assert "데이터베이스" in text
    assert "관계형 모델" in text
    assert "0. 정규화" in text and "1. 키" in text
    assert "specs" in text
