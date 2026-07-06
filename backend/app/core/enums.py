"""공통 열거값(enum) 상수.

기획서 §4의 PostgreSQL ENUM 타입들을 앱 레벨 상수로 정의한다.
DB 컬럼은 이식성/확장성을 위해 VARCHAR로 저장하고, 허용값을 여기서 단일 관리한다.
(blocks.type 처럼 자주 늘어나는 값은 자유 문자열로 둔다 — 기획서 원칙 "확장은 type 추가로".)
"""
from enum import StrEnum


class DocumentStatus(StrEnum):
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class GenStatus(StrEnum):
    PENDING = "pending"
    GENERATING = "generating"
    READY = "ready"
    FAILED = "failed"


class ChapterOrigin(StrEnum):
    BOOK = "book"
    PREREQ = "prereq"


class ContentSource(StrEnum):
    BOOK = "book"           # 📖 책 청크 근거
    AI_PREREQ = "ai_prereq"  # 🤖 책 밖 선행(외부 근거)
    ANALOGY = "analogy"      # 💡 비유(검증 면제, 라벨 강제)


class EdgeKind(StrEnum):
    PREREQUISITE = "prerequisite"
    RELATED = "related"
    APPLICATION = "application"


class MasteryStatus(StrEnum):
    LOCKED = "locked"
    TODO = "todo"
    LEARNING = "learning"
    MASTERED = "mastered"


class ConfidenceLevel(StrEnum):
    SURE = "sure"
    AMBIGUOUS = "ambiguous"
    UNKNOWN = "unknown"


class ServeVariant(StrEnum):
    FULL = "full"
    COMPRESSED = "compressed"
    QUICK = "quick"


class AttemptKind(StrEnum):
    DIAGNOSTIC = "diagnostic"
    LEARN = "learn"
    REVIEW = "review"
    CONNECTION = "connection"


class ProgressStatus(StrEnum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class DiagStatus(StrEnum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
