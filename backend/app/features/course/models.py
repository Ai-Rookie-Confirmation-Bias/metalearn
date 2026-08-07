"""[Entity] 코스 — 자료 여러 개를 한 수업으로 묶는 층.

파싱(문서 층)과 학습(사용자 층) 사이가 비어 있었다. 문서 층은 책 한 권을
혼자 처리할 뿐이라 "교수님 PPT + 교재"를 한 수업으로 합칠 자리가 없었다.

세 가지를 여기서 정한다:

  ① 어떤 자료들을 묶는가        course_documents
  ② 누가 뼈대고 누가 본문인가    course_documents.role
  ③ 이 사람의 목차는 무엇인가    course_topics  ← 문서의 목차를 복사해 고친다

**③이 핵심이다.** doc_topics는 문서 소유라 책 한 권에 목차 한 벌뿐이다.
사용자가 "이 단원은 건너뛰고 저긴 쪼개고"를 하면 원본을 덮어써야 하고,
그러면 같은 책을 보는 다른 사람이 남의 목차를 보게 된다. 원본은 그대로 두고
사람마다 복사본을 갖는다.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class TopicOrigin(StrEnum):
    """이 단원이 어디서 왔는가."""

    BOOK = "book"          # 자료의 목차에서 복사
    INSERTED = "inserted"  # 진단 결과로 끼워 넣은 보강 단원 (책 밖 선수개념)
    MERGED = "merged"      # 여러 단원을 합침
    SPLIT = "split"        # 한 단원을 쪼갬


class TopicPlan(StrEnum):
    """진단 결과로 이 단원을 어떻게 다룰지."""

    NORMAL = "normal"
    SKIP = "skip"      # 이미 아는 단원 — 건너뛴다
    BRIEF = "brief"    # 대충 아는 단원 — 축약
    DEEP = "deep"      # 모르는 단원 — 심화


class Course(Base):
    """수업 하나. 자료 조합 + 그 사람의 목차."""

    __tablename__ = "courses"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),
        nullable=False,
    )

    documents: Mapped[list["CourseDocument"]] = relationship(
        back_populates="course", cascade="all, delete-orphan",
        order_by="CourseDocument.seq",
    )
    topics: Mapped[list["CourseTopic"]] = relationship(
        back_populates="course", cascade="all, delete-orphan",
        order_by="CourseTopic.seq",
    )


class CourseDocument(Base):
    """이 수업에 들어간 자료 하나와 그 역할.

    역할은 자동 제안하고 사용자가 바꾼다:
      - 사용자가 올린 자료는 무조건 뼈대 후보다 (= 내가 배울 범위)
      - 본문까지 겸할 수 있는지는 밀도가 정한다 (documents.chars_per_page)
      - PPT + 교재면 PPT가 뼈대(교수님이 정한 게 시험 범위), 교재가 본문
    """

    __tablename__ = "course_documents"
    __table_args__ = (
        UniqueConstraint("course_id", "document_id", name="uq_course_document"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    # skeleton | body | reference — parsing.models.MaterialRole와 같은 값.
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    # 목차 우선순위. 뼈대가 여럿이면 낮은 번호가 이긴다.
    seq: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    course: Mapped["Course"] = relationship(back_populates="documents")


class CourseTopic(Base):
    """이 사람의 목차 한 줄. **문서 목차의 복사본이다.**

    source_topic_id로 원본을 가리키되 제목·순서는 여기서 자유롭게 바꾼다.
    진단으로 끼워 넣은 보강 단원은 원본이 없으므로 NULL이다.
    """

    __tablename__ = "course_topics"
    __table_args__ = (
        UniqueConstraint("course_id", "seq", name="uq_course_topic_seq"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)

    # 원본 목차. 지워져도 이 단원은 남는다(사용자가 고친 결과물이므로) → SET NULL.
    source_topic_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("doc_topics.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    origin: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=TopicOrigin.BOOK.value
    )
    plan: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=TopicPlan.NORMAL.value
    )
    # 보강 단원이 어떤 개념 때문에 생겼는지. 끊긴 고리 → 이 단원의 근거.
    anchor_concept_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("concepts.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    course: Mapped["Course"] = relationship(back_populates="topics")


class PrereqStatus(StrEnum):
    """이 선수 항목이 정말 '책 밖'인가."""

    PASS = "pass"          # 진짜 밖 — 물어볼 값어치가 있다
    GRAY = "gray"          # 애매 — 목록에 넣되 표시한다
    REJECTED = "rejected"  # 이 코스의 자료가 이미 가르친다


class CoursePrereq(Base):
    """16'단계 — 이 코스를 시작하기 전에 알아야 하는 것 한 줄.

    재료는 문서 소유(documents.prereq_probe)지만 **판정은 코스 소유다.**
    PPT가 요구하는 선수를 같이 올린 교재가 이미 커버할 수 있어서, 자료 조합이
    바뀌면 답이 달라진다.

    거르는 이유: LLM이 **그 책이 가르치는 것을 선수라고 뱉는다.** 실측에서
    정처기 필기 자료에 `데이터베이스 기초`가 선수로 나왔는데 목차 3번이
    "데이터베이스 구축"이었다.

    문턱 0.49는 정답을 아는 21개로 쟀다. 두 무리가 겹치지 않았다:
        책 안 0.509(데이터베이스 개념)~0.828(CIDR 표기)
        책 밖 0.344(OSI 7계층)~0.468(입출력 장치 관리)
    표본이 21개뿐이라 경계 양옆 0.47~0.52는 gray로 빼서 방어한다.
    """

    __tablename__ = "course_prereqs"
    __table_args__ = (
        UniqueConstraint("course_id", "subject", "item", name="uq_course_prereq"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    subject: Mapped[str] = mapped_column(String(256), nullable=False)  # 자료구조
    item: Mapped[str] = mapped_column(String(512), nullable=False)     # 트리와 순회
    why: Mapped[str | None] = mapped_column(Text, nullable=True)
    seq: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    # 과목 안에서 순서가 강제되면 True. 보강 단원이냐 한 꼭지냐를 가르는 축이다.
    ordered: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )

    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=PrereqStatus.PASS.value
    )
    # 되짚기용 — 왜 이렇게 판정했는지. 문턱값을 나중에 옮길 때 이게 근거가 된다.
    similarity: Mapped[float | None] = mapped_column(Float, nullable=True)
    rejected_by: Mapped[str | None] = mapped_column(Text, nullable=True)

    # 사용자 답: known | heard | unknown. 24번 진단이 채운다. 지금은 NULL.
    known: Mapped[str | None] = mapped_column(String(16), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
