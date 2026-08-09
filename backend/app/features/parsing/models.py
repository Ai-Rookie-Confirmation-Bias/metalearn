"""[Entity] 파싱 산출물 스키마.

설계 원칙 세 가지 (docs/PARSING_v3.md):

  ① 문서는 공용이다 — documents에 user_id가 없다. 소유는 user_documents로만.
     같은 교재를 N명이 올려도 지문(fingerprint)이 같으면 파싱은 1회다.

  ② 원문 → 개념 방향이다 — 조각을 전부 목차에 분류한다. 조각 수와 목차별
     합계가 일치해야 하므로 누락이 산술적으로 걸린다. (기존은 개념이 원문을
     가리켜서, 아무도 안 가리키는 원문이 생겨도 알 방법이 없었다.)

  ③ 개념 ↔ 조각은 다대다다 — concept_segments. 같은 개념이 6p·11p·15p에
     나오면 셋 다 남는다. 기존 단수 FK는 첫 등장만 저장했고, 중복 병합 시
     합쳐진 쪽 출처가 통째로 사라졌다.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from pgvector.sqlalchemy import HALFVEC
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import settings
from app.core.database import Base

# pgvector 컬럼 차원. settings가 단일 진실 — 실측으로 확정한 뒤 마이그레이션을
# 만든다. 이 값을 바꾸면 저장된 벡터를 전부 재생성해야 하므로 운영 중 변경 금지.
EMBED_DIM = settings.SOLAR_EMBED_DIM

# 파싱 버전. 파이프라인 로직이 바뀌면 올린다 — 재파싱 대상 판별용.
PARSER_VERSION = "v3.0"


class DocStatus(StrEnum):
    """파이프라인 상태 전이. 실패하면 어느 단계에서 죽었는지 그대로 남는다."""

    PENDING = "pending"
    PARSING = "parsing"        # 1. Document Parse
    REFINING = "refining"      # 3~4. 정제
    SEGMENTING = "segmenting"  # 5~6. 조각 + 임베딩
    TOPICS = "topics"          # 7. 목차 분류
    EXTRACTING = "extracting"  # 8~11. 개념 추출·저장
    READY = "ready"
    FAILED = "failed"


class MaterialRole(StrEnum):
    """자료의 역할. 사용자 자료는 무조건 뼈대가 되고, 밀도가 높으면 본문도 겸한다."""

    SKELETON = "skeleton"    # 뼈대 — 범위와 순서를 정함
    BODY = "body"            # 본문 — 실제 설명 내용
    REFERENCE = "reference"  # 참고 — 출제 경향만 읽음 (기출). 문제로 내지 않음


class DensityGrade(StrEnum):
    """밀도 등급 (12단계). 프리로드에서 설명을 당겨올지 결정하는 스위치."""

    FULL = "full"          # 본문까지 가능
    SKELETON = "skeleton"  # 뼈대만 — 내용은 다른 자료에서


# ─────────────────────────────────────────────────────────────────
# 문서 + 소유
# ─────────────────────────────────────────────────────────────────


class Document(Base):
    """업로드된 자료 한 건. **주인이 없다.**

    소유자를 여기 두면 같은 교재를 3명이 올릴 때 파싱이 3번 돌고, 프리로드
    교과서를 넣을 자리가 없어진다(관리자 계정 편법). 소유는 user_documents로.
    """

    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # 파일 바이트의 sha256. 같은 파일 재업로드 시 파싱을 건너뛰는 근거.
    fingerprint: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True
    )
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    # pdf | pptx | docx | web | audio — 1단계 어댑터 선택에만 쓰인다.
    # 2단계부터는 어떤 형식이었는지 아무도 몰라도 된다.
    source_format: Mapped[str] = mapped_column(String(16), nullable=False)
    storage_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    # private: 올린 사람만 | shared: 링크 공유 | public: 프리로드 카탈로그
    visibility: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="private"
    )

    status: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default=DocStatus.PENDING.value, index=True
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    parser_version: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default=PARSER_VERSION
    )

    # Document Parse 원본. raw_markdown은 보존·디버깅용이고, 파이프라인의
    # 1순위 입력은 refined_elements의 요소 배열이다.
    raw_markdown: Mapped[str | None] = mapped_column(Text, nullable=True)
    # {"elements": [...], "scan": {...}} — 제거 대상은 삭제하지 않고
    # removed="<사유>" 마킹만 한다. 오판해도 마크만 떼면 복구된다.
    refined_elements: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True
    )

    # 12단계 산출물
    density_grade: Mapped[str | None] = mapped_column(String(16), nullable=True)
    # 참고용. 조각 예산의 함수라 자료 밀도를 재지 못한다 — 판정은 아래를 쓴다.
    avg_segment_chars: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # 페이지당 본문 글자수. 뼈대/본문을 가르는 실제 기준 (density.py 주석 참조).
    chars_per_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    concept_coverage: Mapped[int | None] = mapped_column(  # 0~100 (%)
        Integer, nullable=True
    )

    # 12.5단계 산출물 — "이 자료는 무슨 분야고, 그 앞엔 뭐가 필요한가".
    #
    # **문서 소유인 게 핵심이다.** 이 판정이 파이프라인에서 LLM이 흔들리는
    # 유일한 지점인데, 문서에 붙여 두면 지문 재사용이 그대로 먹어서 같은 책은
    # 누가 올리든 같은 판정을 받는다. 코스마다 다시 물으면 매번 달라진다.
    #
    # 책 밖 선수를 찾는 유일한 경로이기도 하다. 끊긴 고리(설명 없는 개념)로
    # 찾는 방식은 폐기했다 — 실측에서 pilgi 55개가 대부분 그 책이 가르치는
    # 내용이었다(목차에 "데이터베이스 구축"이 있는데 `데이터베이스`가 끊긴
    # 고리로 잡히는 식). 책이 언급조차 안 한 선수는 애초에 잡히지 않는다.
    field: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # {"field","level","prereq_subjects":[{"name","why","subtopics":[...],"ordered"}]}
    prereq_probe: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),
        nullable=False,
    )

    topics: Mapped[list["DocTopic"]] = relationship(
        back_populates="document", cascade="all, delete-orphan",
        order_by="DocTopic.seq",
    )
    segments: Mapped[list["DocSegment"]] = relationship(
        back_populates="document", cascade="all, delete-orphan",
        order_by="DocSegment.seq",
    )
    concepts: Mapped[list["Concept"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )
    figures: Mapped[list["DocFigure"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class UserDocument(Base):
    """누가 어떤 문서를 어떤 역할로 쓰는지. 소유 관계는 오직 여기에만 있다."""

    __tablename__ = "user_documents"
    __table_args__ = (UniqueConstraint("user_id", "document_id", name="uq_user_document"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=MaterialRole.SKELETON.value
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


# ─────────────────────────────────────────────────────────────────
# 목차 · 조각 · 문장
# ─────────────────────────────────────────────────────────────────


class DocTopic(Base):
    """7단계 목차 분류 결과. 학습의 단위 — 이거 하나를 통째로 넣어 문제를 만든다.

    개수는 settings.TOPIC_MAX_COUNT(10) 이하로 강제한다. 더 잘게 쪼개면
    학습 단위로 쓸 수 없고, 더 뭉치면 문제 생성 입력이 너무 커진다.
    """

    __tablename__ = "doc_topics"
    __table_args__ = (UniqueConstraint("document_id", "seq", name="uq_topic_seq"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    page_from: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_to: Mapped[int | None] = mapped_column(Integer, nullable=True)

    document: Mapped["Document"] = relationship(back_populates="topics")
    segments: Mapped[list["DocSegment"]] = relationship(
        back_populates="topic", order_by="DocSegment.seq"
    )


class DocSegment(Base):
    """원문 조각. **요약하지 않는다** — 마크다운 원문 그대로다.

    5단계에서 제목을 경계로 묶되 요소는 절대 쪼개지 않아, 표와 수식의
    원자성이 구조적으로 보장된다.
    """

    __tablename__ = "doc_segments"
    __table_args__ = (UniqueConstraint("document_id", "seq", name="uq_segment_seq"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # 7단계 분류 전에는 NULL. 파싱 완료 시점에 NULL이 남아 있으면 실패로 본다.
    # 목차가 지워져도 조각은 원문이므로 살려둔다 → SET NULL.
    topic_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("doc_topics.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    heading: Mapped[str | None] = mapped_column(Text, nullable=True)

    # 드릴다운 좌표 — 2-b 그림 인라인 복원이 이 범위로 그림 위치를 찾는다.
    element_from: Mapped[int | None] = mapped_column(Integer, nullable=True)
    element_to: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_from: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_to: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # 12단계 밀도 계산용. 저장해두면 재집계가 SQL 한 방이다.
    char_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    embedding: Mapped[list[float] | None] = mapped_column(
        HALFVEC(EMBED_DIM), nullable=True
    )

    document: Mapped["Document"] = relationship(back_populates="segments")
    topic: Mapped["DocTopic | None"] = relationship(back_populates="segments")
    sentences: Mapped[list["SegmentSentence"]] = relationship(
        back_populates="segment", cascade="all, delete-orphan",
        order_by="SegmentSentence.seq",
    )
    # 이 조각 안에 있던 그림. `Document.figures`는 문서 전체라 조각별로 다시
    # 묶어야 했다 — 소비자(코스 트리·학습 어댑터)가 조각 단위로 읽는다.
    #
    # ⚠️ cascade를 안 건다. 그림의 FK는 `ondelete="SET NULL"`이라 조각이 지워져도
    #    그림은 문서에 남는다(재파싱 중간 상태에서 이미지가 사라지면 안 된다).
    figures: Mapped[list["DocFigure"]] = relationship(
        back_populates="segment", order_by="DocFigure.char_offset", viewonly=True,
    )


class SegmentSentence(Base):
    """문장 앵커 (5-b). 북마크·드래그·"교재 33p 이 문장" 근거 표시에 쓴다.

    char_start/end는 조각 content 안의 offset이다. 원문을 복사해 두는 게 아니라
    가리키기만 하므로, 조각이 원본이라는 불변식이 유지된다.
    """

    __tablename__ = "segment_sentences"
    __table_args__ = (UniqueConstraint("segment_id", "seq", name="uq_sentence_seq"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    segment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("doc_segments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    char_start: Mapped[int] = mapped_column(Integer, nullable=False)
    char_end: Mapped[int] = mapped_column(Integer, nullable=False)

    segment: Mapped["DocSegment"] = relationship(back_populates="sentences")


# ─────────────────────────────────────────────────────────────────
# 개념 그래프
# ─────────────────────────────────────────────────────────────────


class Concept(Base):
    """조각에서 뽑은 개념.

    (document_id, normalized_name) 유니크가 중복 방어 ①이다. 정규화는
    괄호와 **공백을 전부** 제거한다 — "일계도함수"와 "일계 도함수"는 임베딩
    유사도가 0.75~0.81이라 문턱(0.92)에 절대 안 걸린다.
    """

    __tablename__ = "concepts"
    __table_args__ = (
        UniqueConstraint("document_id", "normalized_name", name="uq_concept_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # 소속 목차는 하나. 개념이 여러 목차에 걸치면 첫 등장 목차로 귀속시킨다
    # (원문 출처는 concept_segments가 전부 들고 있으므로 정보 손실이 아니다).
    topic_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("doc_topics.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_name: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    definition: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 전역 개념 사전 키 (13단계). 과목을 넘어 매칭·프리로드 연결에 쓴다.
    global_key: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    # book: 원문에 설명이 있는 개념 | ai_prereq: 선수개념으로만 등장(교재 밖)
    source: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="book"
    )
    # 근거 문장 — [[조각 seq, 문장 seq], …]. 5-b가 만든 segment_sentences를
    # 가리킨다. 조각 번호를 함께 두는 이유: 개념 하나가 조각 여러 개에 걸치는데
    # (concept_segments가 다대다다) 문장 번호는 조각 안에서만 유효해서, 번호만
    # 남기면 어느 조각의 몇 번째 문장인지 알 수 없다.
    # 빈 배열은 "LLM이 근거를 특정하지 못함"이고 NULL은 "추출 시점에 이 기능이
    # 없던 문서"다 — 둘을 구분해야 커버리지 통계가 거짓말을 안 한다.
    evidence_sentences: Mapped[list[Any] | None] = mapped_column(
        JSONB, nullable=True
    )
    embedding: Mapped[list[float] | None] = mapped_column(
        HALFVEC(EMBED_DIM), nullable=True
    )

    document: Mapped["Document"] = relationship(back_populates="concepts")
    segment_links: Mapped[list["ConceptSegment"]] = relationship(
        back_populates="concept", cascade="all, delete-orphan"
    )


class ConceptSegment(Base):
    """⭐ 개념 ↔ 조각 다대다. 이 설계의 핵심 수정.

    같은 개념이 6p·11p·15p에 나오면 행 3개가 남는다. 중복 병합 시에도
    합쳐지는 쪽의 링크를 **전부 이관**한다 — 기존처럼 버리면 안 된다.
    """

    __tablename__ = "concept_segments"
    __table_args__ = (
        UniqueConstraint("concept_id", "segment_id", name="uq_concept_segment"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    concept_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("concepts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    segment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("doc_segments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # 조각 안에서 이 개념이 실제로 설명되는 문장 (5-b 이후 채움).
    sentence_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("segment_sentences.id", ondelete="SET NULL"),
        nullable=True,
    )

    concept: Mapped["Concept"] = relationship(back_populates="segment_links")


class ConceptEdge(Base):
    """개념 간 관계. prerequisite(선후관계)가 근본 원인 진단의 근거가 된다."""

    __tablename__ = "concept_edges"
    __table_args__ = (
        UniqueConstraint(
            "from_concept_id", "to_concept_id", "kind", name="uq_concept_edge"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    from_concept_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("concepts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    to_concept_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("concepts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # prerequisite: from을 알아야 to를 이해 | contains: 상하위 | related: 인접
    kind: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="prerequisite"
    )


class ConceptLink(Base):
    """⭐ 18단계 — **다른 문서**의 같은 개념끼리 묶는다. (concept_edges는 문서 안)

    PPT는 "서브넷"이라는 표제어만 있고 교재에 그 설명이 세 쪽 있다. 이걸 이어야
    "교수님 PPT 순서로 가되 설명은 교재에서" 가 된다.

    **문서쌍 소유다.** 코스가 아니라. 문서가 공용이라 같은 두 책을 쓰는 다음
    사람이 다시 계산하지 않아도 되고, 뼈대/본문 역할은 코스마다 뒤집히므로
    방향을 여기 박으면 안 된다. 그래서 **무방향으로 저장하고**(항상 a<b로
    정규화) 방향은 코스가 정한다.

    문턱은 실측이다 — pilgi 452개를 ryan 578개에 전부 대조했다:
        0.85 이상   도커↔Docker, 트랜잭션↔트랜잭션      → same
        0.75~0.85   MVC↔모델-뷰-컨트롤러, IDS↔침입탐지  → related (상하위 포함)
        0.70~0.75   정규화↔정규화(맞음)와 블루스나프↔블루버그(틀림)가 섞임
        0.70 미만   MD4↔MD5, 자료구조↔데이터베이스      → 버림
    0.70~0.75는 이름만 닮은 딴것이 섞여 임베딩으로 못 가른다. LLM에게 묻는다.

    dedup의 0.92를 쓰지 않는 이유: 그건 한 문서 안 **동일 개념 병합**이라
    보수적이어야 한다. 여기는 "설명을 가져올 만한가"라 상위 개념도 쓸모가 있다.
    """

    __tablename__ = "concept_links"
    __table_args__ = (
        UniqueConstraint("concept_a_id", "concept_b_id", name="uq_concept_link"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # 항상 a < b (문자열 비교). 무방향이라 (x,y)와 (y,x)가 따로 쌓이면 안 된다.
    concept_a_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("concepts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    concept_b_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("concepts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    similarity: Mapped[float] = mapped_column(Float, nullable=False)
    # same: 같은 개념 | related: 상하위·인접
    kind: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="same"
    )
    # embed: 임베딩만으로 확정 | llm: 회색지대라 LLM이 확인해 줌
    verified_by: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="embed"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class DocumentPair(Base):
    """문서쌍 연결 계산이 끝났다는 표시.

    concept_links가 비어 있는 게 "아직 안 쟀다"인지 "재봤는데 겹치는 개념이
    없다"인지 구별해야 한다. 없으면 코스를 열 때마다 452회 조회를 다시 돈다.
    """

    __tablename__ = "document_pairs"
    __table_args__ = (
        UniqueConstraint("document_a_id", "document_b_id", name="uq_document_pair"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_a_id: Mapped[uuid.UUID] = mapped_column(  # 항상 a < b
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document_b_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    link_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


# ─────────────────────────────────────────────────────────────────
# 그림
# ─────────────────────────────────────────────────────────────────


class DocFigure(Base):
    """Document Parse가 크롭해 준 그림·도표.

    AI가 그리는 게 아니라 원문에서 잘라온 것이라 환각이 0이다.

    파싱 단계에서 설명(description)을 만들지 않는다. 300p 교재면 그림이
    30~80개인데 실제로 화면에 뜨는 건 10~20개뿐이고, 대부분은 주변 원문에
    설명이 이미 있어 이미지를 볼 필요가 없다. 그래서 여기서는 호출 0회로
    context_text와 needs_vision만 준비해 둔다.
    """

    __tablename__ = "doc_figures"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # 조각 확정(5단계) 후 요소 범위로 역매칭해 채운다.
    segment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("doc_segments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    page: Mapped[int] = mapped_column(Integer, nullable=False)
    element_id: Mapped[int] = mapped_column(Integer, nullable=False)
    # 조각 content 안에서 이 그림이 원래 있던 위치(문자 offset).
    # 프론트가 본문을 여기서 끊고 이미지를 끼우면 원문 흐름이 복원된다.
    # 없으면 그림이 전부 조각 맨 아래로 몰린다.
    char_offset: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    category: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="figure"
    )
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)

    # 그림 앞뒤 인접 요소의 원문. 순수 로직으로 공짜로 뽑는다.
    # 기존은 화면에 띄울 때마다 DB를 다시 뒤졌다.
    context_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 주변 텍스트가 짧거나 · 캡션이 없거나 · 차트면 true.
    # true인 소수(5~10개)만 나중에 EXAONE 비전으로 실제 이미지를 본다.
    needs_vision: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    # 생성된 설명 캐시 (파싱 파이프라인 밖에서 채움).
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    mime: Mapped[str] = mapped_column(
        String(64), nullable=False, server_default="image/png"
    )
    data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)

    document: Mapped["Document"] = relationship(back_populates="figures")
    # `DocSegment.figures`의 짝. 조각이 지워지면 FK가 NULL이 되므로 없을 수 있다.
    segment: Mapped["DocSegment | None"] = relationship(
        back_populates="figures", viewonly=True,
    )


# ─────────────────────────────────────────────────────────────────
# 전역 개념 사전 (M3)
# ─────────────────────────────────────────────────────────────────


class GlobalConcept(Base):
    """과목·문서를 넘는 개념 사전.

    "내 PPT의 OSI 7계층"과 "공용 네트워크 교과서의 OSI 7계층"을 잇는 고리다.
    이게 없으면 뼈대만 있는 자료에 본문을 당겨올 수 없다.
    """

    __tablename__ = "global_concepts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    key: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    canonical_name: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(
        HALFVEC(EMBED_DIM), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
