"""코스 입출력 스키마."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CourseCreate(BaseModel):
    # users 테이블이 아직 없어 클라이언트가 직접 준다. auth가 들어오면 토큰에서.
    user_id: uuid.UUID
    document_ids: list[uuid.UUID] = Field(..., min_length=1)
    title: str | None = None
    # 비우면 밀도로 제안한다. {document_id: skeleton|body|reference}
    roles: dict[uuid.UUID, str] | None = None


class CourseDocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    document_id: uuid.UUID
    role: str
    seq: int


class CourseTopicOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    seq: int
    title: str
    origin: str
    plan: str
    source_topic_id: uuid.UUID | None = None
    anchor_concept_id: uuid.UUID | None = None
    note: str | None = None


class CourseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    title: str
    documents: list[CourseDocumentOut] = []
    topics: list[CourseTopicOut] = []


class PrereqOut(BaseModel):
    """이 코스를 시작하기 전에 알아야 하는 것 한 줄.

    status가 셋인 이유 — 유사도는 "비슷한 이름의 개념이 있나"를 재지 "이걸
    가르치나"를 못 잰다. 확실한 양 끝(0.75 이상 기각 / 0.50 미만 통과)만 임베딩이
    가르고 가운데는 LLM에게 묻되, **LLM은 항목을 지우지 못한다**(gray로만 표시).
    화면은 pass를 그냥 보여주고 gray는 "자료에 조금 나옴"으로 표시하며 rejected는
    숨긴다(디버그로만 본다).
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    subject: str
    item: str
    why: str | None = None
    seq: int
    # 하위 항목 사이 순서가 강제되면 True → 보강 '단원', 아니면 한 '꼭지'.
    ordered: bool
    # pass | gray | rejected
    status: str
    # 되짚기용. 어떤 개념에 얼마나 가까워서 그렇게 판정했는가.
    similarity: float | None = None
    rejected_by: str | None = None
    # 24번 진단이 채운다: known | heard | unknown
    known: str | None = None


class BodyRefOut(BaseModel):
    """18단계가 붙인 것 — 이 개념을 **다른 자료**가 설명하는 곳.

    뼈대(PPT)에는 표제어만 있고 본문(교재)에 설명이 세 쪽 있는 상황을 잇는다.
    `kind`가 related면 상위·하위 개념이라 설명이 조금 넓거나 좁을 수 있다.
    """

    concept_id: uuid.UUID
    document_id: uuid.UUID
    filename: str
    name: str
    definition: str | None = None
    similarity: float
    kind: str          # same | related
    verified_by: str   # embed | llm
    # 그 개념이 설명되는 원문 조각. 화면이 이걸 그대로 본문으로 쓴다.
    segments: list["BodySegmentOut"] = Field(default_factory=list)


class BodySegmentOut(BaseModel):
    """원문 조각 하나. **자르지 않고 통째로 준다.**

    어느 자료 것인지 밝힌다 — 단원 하나에 뼈대 조각과 본문 조각이 함께 들어오고,
    화면이 "AI가 지어낸 게 아니라 이 책의 이 쪽"을 보이려면 출처가 있어야 한다.
    """

    id: uuid.UUID
    seq: int
    heading: str | None = None
    content: str
    page_from: int | None = None
    page_to: int | None = None
    document_id: uuid.UUID | None = None
    filename: str | None = None
    # skeleton | body — 목차 순서를 정한 자료인가, 설명을 대는 자료인가.
    role: str = "skeleton"


class CourseConceptOut(BaseModel):
    """뼈대 자료의 개념 하나 + 본문 자료에서 끌어온 설명."""

    id: uuid.UUID
    name: str
    definition: str | None = None
    source: str
    global_key: str | None = None
    document_id: uuid.UUID
    filename: str
    segment_seqs: list[int] = Field(default_factory=list)
    prerequisite_ids: list[uuid.UUID] = Field(default_factory=list)
    # 뼈대 자료 안에서의 근거 위치(조각/문장/글자 offset).
    evidence: list[dict] = Field(default_factory=list)
    # 다른 자료가 이 개념을 설명한다면 여기 붙는다. 유사도 높은 순.
    body: list[BodyRefOut] = Field(default_factory=list)


class CourseTopicNode(BaseModel):
    id: uuid.UUID
    seq: int
    title: str
    origin: str
    plan: str
    # 복사 원본(doc_topics). 보강 단원은 없으므로 NULL.
    source_topic_id: uuid.UUID | None = None
    # 이 단원이 뼈대 자료의 몇 쪽인가. 조각들의 범위를 그대로 합친 값이고
    # 추정하지 않는다 — 화면이 "p.51-53"으로 원문을 짚어줄 때 쓴다.
    # 보강 단원은 원본이 없으므로 둘 다 NULL이다.
    page_from: int | None = None
    page_to: int | None = None
    concepts: list[CourseConceptOut] = Field(default_factory=list)
    segments: list[BodySegmentOut] = Field(default_factory=list)


class CourseTree(BaseModel):
    """코스 전체 — **뼈대 목차 순서로 가되 설명은 본문 자료에서.**

    문서 트리(GET /parsing/documents/{id}/tree)와 다른 점이 이것이다.
    문서 트리는 책 한 권 안에서만 보고, 여기는 코스에 묶인 자료 전부를 본다.
    """

    course_id: uuid.UUID
    title: str
    # 목차를 제공한 자료. 여기 목차 순서가 곧 학습 순서다.
    skeleton_document_id: uuid.UUID | None = None
    # 설명을 대는 자료들.
    body_document_ids: list[uuid.UUID] = Field(default_factory=list)
    topics: list[CourseTopicNode] = Field(default_factory=list)
    # 몇 개 개념에 본문이 붙었나. 자료 조합이 쓸모 있는지 한눈에 보는 값.
    linked_concepts: int = 0
    total_concepts: int = 0


class GapOut(BaseModel):
    """끊긴 고리 하나 — 책이 필요하다고 하는데 설명이 없는 개념."""

    concept_id: uuid.UUID
    name: str
    global_key: str | None = None
    definition: str | None = None
    # 이 개념을 선수로 부르는 개념 수 / 그 개념들이 속한 단원 수.
    # 단원 수가 많을수록 "여러 군데서 필요한 기초" → 보강 단원 값어치가 크다.
    refs: int
    topics: int


# ── 24 진단 ──────────────────────────────────────────────────────


class PrereqItemOut(BaseModel):
    """진단 화면이 물어볼 항목 하나."""

    id: uuid.UUID
    item: str
    why: str | None = None
    # pass | gray — rejected는 애초에 안 내려간다(자료가 이미 가르친다).
    status: str
    known: str | None = None


class PrereqSubjectOut(BaseModel):
    subject: str
    # 하위 항목 사이 순서가 강제되면 보강 '단원', 아니면 한 '꼭지'.
    ordered: bool
    items: list[PrereqItemOut] = Field(default_factory=list)


class DiagnosticSetupOut(BaseModel):
    """진단 화면 ①~④에 필요한 것 전부. LLM을 안 부르므로 즉시 뜬다."""

    course_id: uuid.UUID
    # 12.5가 판정한 분야. 화면 ②가 이걸 확인받는다 — 자동 검증이 없는 값이라
    # 여기가 유일한 검증 창구다.
    field: str | None = None
    documents: list[str] = Field(default_factory=list)
    goal: str | None = None
    deadline_weeks: int | None = None
    style: str | None = None
    diagnosed_at: datetime | None = None
    subjects: list[PrereqSubjectOut] = Field(default_factory=list)


class DiagnosticCardsOut(BaseModel):
    """③ 같은 개념을 네 형식으로. 고른 것이 `style`이 된다.

    ⚠️ 화면 문구는 "당신에게 맞는 학습법"이 아니라 **"어떤 설명이 읽기 편한가"**
    여야 한다. 스타일 맞춤에 학습 효과 근거는 없다(Pashler 2008) — 이건 성취가
    아니라 이탈을 막는 장치다.
    """

    concept: str | None = None
    # metaphor | definition | table | why. 생성이 실패하면 빈 dict다.
    cards: dict[str, str] = Field(default_factory=dict)


class DiagnosticConfigIn(BaseModel):
    # exam | work | interest
    goal: str | None = None
    deadline_weeks: int | None = None
    # metaphor | definition | table | why
    style: str | None = None


class SubjectAnswersIn(BaseModel):
    """④-1 과목 단위 답. `{과목명: known|heard|unknown}`."""

    answers: dict[str, str]


class SubjectAnswersOut(BaseModel):
    """펼쳐서 더 물어야 할 과목 — "들어봤다"라고 한 것들.

    아는 것과 모르는 것은 더 물어도 얻을 게 없다. 애매한 것만 갈라낸다.
    """

    expand: list[str] = Field(default_factory=list)
    setup: DiagnosticSetupOut


class PrereqAnswersIn(BaseModel):
    """④-2 펼친 과목의 항목별 답. `{prereq_id: known|heard|unknown}`."""

    answers: dict[uuid.UUID, str]


class ProbeOut(BaseModel):
    """⑤ 확인 문항 하나. **정답은 우리가 정했고 LLM은 오답만 만들었다.**

    한 번에 다 오지 않는다 — 답을 받아야 다음이 정해지는 계층 탐색이라,
    화면은 **빈 배열이 올 때까지** `GET → POST`를 반복한다.
    """

    prereq_id: uuid.UUID
    subject: str
    item: str
    stem: str
    choices: list[str] = Field(default_factory=list)
    answer_index: int


class ProbeResultsIn(BaseModel):
    # {prereq_id: 맞았나}
    results: dict[uuid.UUID, bool]


class ProbeGradeOut(BaseModel):
    """채점 결과. `subjects_left`가 0이면 진단이 끝났다.

    한 답이 구간을 통째로 정한다 — 순서가 있는 과목이라 맞힌 자리 아래는 전부
    안다, 틀린 자리 위는 전부 모른다다.
    """

    graded: int = 0
    subjects_left: int = 0
