"""커리큘럼 API 응답 스키마.

화면 셋에 맞춰 셋으로 나눈다. 한 응답에 전부 말아 넣지 않는다 —
목차 하나만 보는 화면이 화면 단위 251개를 다 받을 이유가 없다.

    자료   문서 제목 · 준비도 · 목차 목록
    목차   그 목차의 화면 목록
    화면   학습 콘텐츠(설명·인출)

내부 필드명 `section*` 은 API 호환용. 도메인 말은 화면이다.

**판단은 전부 백엔드에서 끝낸다.** `reason`은 규칙이 만든 문장을 그대로 싣고,
프론트는 있으면 ⚡와 함께 찍고 없으면 안 찍는다. 조건 분기를 화면에 두지 않는
게 이 설계의 요점이다 — 판단을 규칙이 하므로 이유를 쓸 수 있다는 서비스 전제가
화면까지 이어져야 한다.
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict


def _camel(s: str) -> str:
    head, *rest = s.split("_")
    return head + "".join(w.capitalize() for w in rest)


class _Camel(BaseModel):
    model_config = ConfigDict(alias_generator=_camel, populate_by_name=True)


class ChapterBrief(_Camel):
    """자료 화면의 목차 한 줄."""

    index: int
    title: str
    pages: str = ""
    sections_total: int
    sections_done: int
    # untouched | learning | weak | shaky | solid
    status: str
    status_label: str
    ratio: float  # 이해도 — 시도한 절만으로 낸다
    progress: float  # 진도 — 얼마나 훑었나. 이해도와 다르다
    recall: float = 0.0  # 회상 강도 — 지금도 꺼내지나(망각곡선)
    sections_due: int = 0  # 🔁 복습이 필요한 절 수
    mode: str  # deep | normal | compressed
    # ✚ 진단이 끼운 보강 단원인가. **교재에 없던 내용**이라 화면이 구분해
    # 보여야 한다 — 원문(📎)도 없다.
    inserted: bool = False
    # ⚡ 왜 분량이 늘거나 줄었는지. 아직 근거가 없으면 빈 문자열
    reason: str = ""


class DocumentOut(_Camel):
    """[화면 1] 내 자료."""

    doc_id: str
    title: str
    # 준비도 = 이해도 × 진도 × 회상 강도. **네 출처가 모여 나오는 하나의 값.**
    readiness: float
    # 망각을 뺀 값. 준비도가 낮은 게 "잊은 것"인지 "아직 모르는 것"인지 가른다.
    understanding: float = 0.0
    complete: bool
    sections_total: int
    remaining_sections: int
    sections_due: int = 0  # 🔁 복습이 필요한 절 수
    estimated_minutes: int
    weakest_chapter: int | None = None
    # 출처별 푼 문항 수 (diagnostic·retrieval·review·formative).
    # 누적이 **어디서 왔는지** 화면에 보여주는 값이다.
    by_kind: dict[str, int] = {}
    chapters: list[ChapterBrief]
    # **기본 제공 자료인가.** 주인이 없어 누구 책장에나 뜨는 것 — 공개 교재
    # (`visibility='public'`)와 파일 픽스처가 여기 해당한다.
    #
    # 책장이 이걸로 두 칸을 가른다. 안 가르면 "내가 올린 적 없는 책이 왜
    # 내 책장에 있지"가 되고, 그게 촬영에서 그대로 잡힌다(실측: 시연 수업
    # 셋에 픽스처 셋이 섞여 일곱 권).
    shared: bool = False


class IngestOut(_Camel):
    """파싱 문서를 학습 store에 올린 결과."""

    doc_id: str
    title: str
    chapters: int
    sections: int
    source: str = "parsing"


class SectionOut(_Camel):
    """목차 화면의 절 한 줄."""

    section_id: str
    order: int
    title: str
    concepts: list[str]
    # ⚡ 왜 이 개념들이 한 화면에 묶였는지. 규칙이 만든 문장 그대로
    reason: str
    page: str = ""
    status: str
    status_label: str
    attempts: int
    improving: bool
    weak_concepts: list[str] = []
    recall: float = 0.0  # 회상 강도 — 0에 가까울수록 잊혀가는 절
    needs_review: bool = False  # 🔁 복습 대상
    # 출처별 푼 문항 수. "진단 2 · 학습 5 · 복습 1"로 쓴다
    by_kind: dict[str, int] = {}
    # ↻ 우리가 끼운 보충 화면. 교재에 원래 있던 화면과 **구분해서** 보여준다 —
    # 안 그러면 학습자가 원문에 있던 내용이라고 오해한다. 진도 분모에도 안 든다.
    inserted: bool = False
    # 🖼 이 화면에 딸린 교재 그림 수. 목록에서 배지로 쓴다 — 그림이 있는 화면은
    # 텍스트만 있는 화면과 읽는 품이 다르다. 개수만 준다(이미지는 화면을 열 때).
    figure_count: int = 0


class ChapterOut(_Camel):
    """[화면 2] 목차 하나 — 형이 그린 화면."""

    doc_id: str
    doc_title: str
    index: int
    title: str
    pages: str = ""
    # ✚ 진단이 끼운 보강 단원 (교재에 없던 내용)
    inserted: bool = False
    readiness: float  # 문서 전체 준비도(머리에 계속 보인다)
    ratio: float
    progress: float
    recall: float = 0.0
    sections_due: int = 0
    mode: str
    reason: str = ""
    weak_concepts: list[str] = []
    sections: list[SectionOut]
    # 목차 마지막 항목(단원 평가)이 열렸는가. **화면이 판정하지 않는다** —
    # 문턱을 프론트에도 두면 규칙이 두 곳에 생기고 언젠가 갈라진다.
    formative_ready: bool = False
    # 잠겼을 때 얼마나 더 해야 하는지. 열려 있으면 빈 문자열
    formative_reason: str = ""


class BlockOut(_Camel):
    """학습 블록 하나. `content`는 종류마다 모양이 달라 그대로 싣는다.

        concept  {text}
        analogy  {text, label}
        cloze    {sentence, answer}
        mcq      {question, options, answer, explanation}
    """

    type: str
    content: dict
    concept_keys: list[str]


class FigureOut(_Camel):
    """화면에 딸린 그림 하나.

    `url`은 파싱이 서빙한다 — 이미지 바이트를 우리 응답에 실으면 자료 하나에
    1.6MB짜리도 있어서 레슨 응답부터 느려진다.
    """

    figure_id: str
    page: int
    caption: str = ""
    # 파싱이 "텍스트만으로 불완전"이라 본 그림. 화면이 더 크게 보여줄 근거.
    needs_vision: bool = False
    url: str = ""


class LessonOut(_Camel):
    """[화면 3] 절 하나 — 설명·비유·인출 + 📎 원문 + 그림."""

    section_id: str
    doc_id: str
    chapter_index: int
    chapter_title: str
    title: str
    concepts: list[str]
    reason: str
    page: str = ""
    status: str
    status_label: str
    blocks: list[BlockOut]
    # 📎 교재 원문 그대로. 요약이 아니다 — 요약을 넣으면 또 다른 AI 생성물이 되어
    # "AI가 지어낸 해설이 아니라 교재의 그 문장"이라는 근거가 무너진다.
    source: str = ""
    # 이 화면 원문 구간에 있던 그림. 원문과 같은 이유로 담는다 — 교재에 실제로
    # 있던 그림이라는 게 설명의 근거다. 바이트는 안 싣고 id만 준다.
    figures: list[FigureOut] = []
    # ⚡ 최근 틀린 개념 중 **이 설명이 실제로 엮은 것**. 요청한 것이 아니라
    # 본문에 들어간 것만 담는다 — 이유만 뜨고 본문이 그대로면 거짓말이 된다.
    tied_in: list[str] = []
    # 생성 품질. 화면에 그대로 쓰진 않지만 개발 중 확인용으로 내보낸다.
    covered: int = 0
    missing: list[str] = []
    retrieval_gap: list[str] = []
    generated: bool = True


class FormativeOut(_Camel):
    """[화면 4] 단원 평가 — 화면을 가로질러 구별할 수 있는가.

    **학습은 안 잠그고 평가만 잠근다.** `locked`가 참이면 `blocks`는 비어 있고
    `reason`이 얼마나 더 봐야 하는지 말한다. 진도로만 잠근다 — 이해도로 잠그면
    못 하는 사람일수록 확인할 기회가 사라진다.
    """

    doc_id: str
    chapter_index: int
    chapter_title: str
    locked: bool = False
    # 🔒 왜 잠겼는지 + 얼마나 더 해야 하는지. 열려 있으면 빈 문자열
    reason: str = ""
    progress: float = 0.0
    blocks: list[BlockOut] = []
    # 화면을 가로지른 문항 수 / 전체. 낮으면 인출 몰아보기와 다르지 않다
    crossing: int = 0
    # 이 평가가 실제로 확인하는 약점 개념(요청이 아니라 문항에 들어간 것)
    covered_weak: list[str] = []
    generated: bool = True


class ReviewItem(_Camel):
    """복습할 화면 하나 + 그 화면의 새 문항."""

    section_id: str
    title: str
    chapter_index: int
    chapter_title: str
    # 회상 강도. 0.6 아래로 내려온 것들이 여기 온다
    recall: float
    # 마지막으로 맞힌 뒤 며칠. 화면에 "3일 전 학습"으로 쓴다
    days_since: float
    blocks: list[BlockOut] = []


class ReviewOut(_Camel):
    """[화면 5] 복습 큐 — 망각곡선이 불러온 것들.

    ⚠️ **설명은 안 준다.** 복습은 잊혀가는 걸 되살리는 자리고, 설명을 다시
    보여주면 재인이 되어 "읽었으니 안다"는 착각만 늘린다.

    ⚠️ **한 번도 못 맞힌 화면은 여기 없다.** 그건 잊은 게 아니라 아직 모르는
    것이라 처방이 다르다(보충 화면·설명 안 ⚡가 맡는다).
    """

    doc_id: str
    # 시연용 시계 이동(일). 0이면 지금. **가짜 데이터가 아니라 진짜 곡선을
    # 옮겨 보는 것**이라 심사에서 그대로 설명할 수 있다.
    shifted_days: int = 0
    total_due: int = 0
    items: list[ReviewItem] = []


class AnswerIn(_Camel):
    """시도 한 건. **네 출처가 전부 이 문으로 들어온다.**

    `kind`를 안 받으면 나중에 진단·복습·형성을 붙일 때 가중을 못 준다. 지금
    화면에서 오는 건 전부 인출이라 기본값을 그렇게 뒀다.
    """

    correct: bool
    concept_key: str | None = None
    # diagnostic | retrieval | review | formative
    kind: str = "retrieval"


class AnswerOut(_Camel):
    """기록 직후 바뀐 것만 돌려준다 — 화면이 그 자리에서 갱신되도록."""

    section_id: str
    status: str
    status_label: str
    attempts: int
    improving: bool
    recall: float = 0.0
    chapter_ratio: float
    chapter_mode: str
    chapter_reason: str = ""
    readiness: float
    understanding: float = 0.0


# ── 메타인지 분석 ────────────────────────────────────────────────


class AnalysisDoc(_Camel):
    """분석 화면이 보는 자료 한 권."""

    doc_id: str
    title: str
    readiness: float
    understanding: float
    sections_total: int
    sections_done: int
    sections_due: int
    # 가장 약한 목차 — 없으면 아직 판정할 자격이 없다는 뜻(MIN_WEIGHT 미달)
    weakest_chapter: str | None = None
    weak_concepts: list[str] = []
    by_kind: dict[str, int] = {}
    # ✚ 진단이 목차 앞에 끼운 보강 단원 수. **진단이 한 일은 여기 있다** —
    # 점수를 쌓는 게 아니라 배울 순서를 바꾼다.
    inserted_chapters: int = 0


class AnalysisOut(_Camel):
    """내 학습 전체를 가로지른 요약.

    화면 하나가 이걸 다 보여준다 — **네 출처가 하나로 모인다**는 게 이 서비스의
    주장이고, 그 주장이 눈에 보이는 유일한 자리다.

    ⚠️ `readiness`는 자료별 값을 **화면 수로 가중**해 합친다. 세 화면짜리와
       124화면짜리를 단순 평균하면 작은 자료가 전체를 흔든다.
    """

    readiness: float
    understanding: float
    sections_total: int
    sections_done: int
    sections_due: int
    attempts_total: int
    # 진단·인출·복습·형성이 각각 몇 건인가. **비어 있는 출처가 곧 빈 구멍이다.**
    by_kind: dict[str, int] = {}
    documents: list[AnalysisDoc] = []
    # 자료를 가로질러 모은 약점 — (개념, 몇 번 틀렸나)
    weak_concepts: list[tuple[str, int]] = []
    # ✚ 진단이 끼운 보강 단원 총합.
    #
    # ⚠️ `by_kind["diagnostic"]`은 **구조적으로 늘 0이다.** 진단(24)은 문항을
    #    풀려 점수를 쌓는 게 아니라 `course_prereqs`에 "안다/모른다"를 남기고
    #    그 결과로 목차를 바꾼다. 화면이 "진단 기록이 아직 없어요"라고 말하면
    #    사실과 다르다 — 안 한 게 아니라 **다른 축을 잰다.**
    #    그래서 진단이 한 일을 이 숫자로 보여준다.
    inserted_chapters: int = 0
