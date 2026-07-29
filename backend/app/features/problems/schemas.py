"""[2.DTO] 문제 생성 에이전트 입출력 계약.

입력 = 파싱 에이전트 → 생성 에이전트 (개념 구간 + 원문).
출력 = 생성 에이전트 → 검증 에이전트 / DB (문항 + 근거).
"""
from enum import IntEnum

from pydantic import BaseModel, Field, field_validator


class Level(IntEnum):
    """블룸 단계 축약 — L1 암기 / L2 적용 / L3 심화."""

    RECALL = 1
    APPLY = 2
    DEEP = 3


# ── 입력 계약 (파싱 → 생성) ─────────────────────────────────────────
class ConceptInput(BaseModel):
    """파싱이 넘기는 개념 구간 = **소제목 단위**(챕터 통째 아님).

    소제목 단위로 받는 이유: source_text가 대조 범위이므로, 챕터 전체를 받으면
    "페이지 교체" 문항이 "기억장치 관리" 구절을 근거로 붙여도 통과해 버린다.
    구간이 좁을수록 근거 대조가 정확해지고 커버리지도 균등해진다.
    소제목을 못 쪼갠 챕터는 섹션 1개로 보내면 되므로 파싱 쪽 실패에도 안전하다.
    """

    concept_id: str
    title: str  # 소제목 (예: "기억장치 관리 전략")
    order: int = 0
    keywords: list[str] = Field(default_factory=list)
    # ★ source_text 필수 — 키워드만 받으면 LLM이 자기 지식으로 지어낸다.
    # ★ 원문 그대로여야 한다(### 소제목·표 파이프 보존) — 근거 대조 대상이다.
    source_text: str = Field(min_length=1)
    source_page: int | None = None
    # 진도 화면은 챕터 × 레벨로 묶어 보여주므로 소속 챕터를 함께 받는다.
    chapter_id: str | None = None
    chapter_title: str | None = None


class GenerateProblemsRequest(BaseModel):
    subject: str
    concepts: list[ConceptInput] = Field(min_length=1)
    # 레벨별 문항 수 (데모 튜닝값 — 추후 유형 배분과 함께 조정)
    per_level: int = Field(default=2, ge=1, le=10)


# ── 출력 계약 (생성 → 검증/DB) ──────────────────────────────────────
class Problem(BaseModel):
    level: Level
    type: str = "mcq"  # v1 = mcq. 규칙채점형(order/match/classify…)은 확장.
    question: str
    options: list[str] = Field(min_length=2)
    # 정답: 옵션 원문과 정확히 일치해야 함 (서빙 시 스트립·채점 대조 기준).
    answer: str
    explanation: str
    # ★ 검증 에이전트 v1의 입력 — 원문에 실재하는 근거 문구.
    source_evidence: str

    @field_validator("answer")
    @classmethod
    def _answer_in_options(cls, v: str, info: object) -> str:
        # answer가 options 안에 있는지 보장 (LLM이 라벨/번호로 답하는 사고 차단).
        options = getattr(info, "data", {}).get("options") or []
        if options and v not in options:
            raise ValueError(f"answer '{v}' must match one of options {options}")
        return v


class ConceptProblems(BaseModel):
    concept_id: str
    title: str
    # 진도 집계 단위(챕터 × 레벨)를 위해 소속 챕터를 그대로 실어 보낸다.
    chapter_id: str | None = None
    chapter_title: str | None = None
    problems: list[Problem] = Field(default_factory=list)
    # 원문이 부족하면 억지로 채우지 않고 정직하게 명시한다.
    # ★ 진도 엔진 입력: "이 개념엔 L3가 없음"을 알아야 L2 통과=완료로 처리한다.
    coverage_note: str = ""


class GenerateProblemsResponse(BaseModel):
    subject: str
    results: list[ConceptProblems] = Field(default_factory=list)
