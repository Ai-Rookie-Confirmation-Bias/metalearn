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


class ChapterOut(_Camel):
    """[화면 2] 목차 하나 — 형이 그린 화면."""

    doc_id: str
    doc_title: str
    index: int
    title: str
    pages: str = ""
    readiness: float  # 문서 전체 준비도(머리에 계속 보인다)
    ratio: float
    progress: float
    recall: float = 0.0
    sections_due: int = 0
    mode: str
    reason: str = ""
    weak_concepts: list[str] = []
    sections: list[SectionOut]


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


class LessonOut(_Camel):
    """[화면 3] 절 하나 — 설명·비유·인출 + 📎 원문."""

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
