"""[2.DTO] 문제 생성 파이프라인의 모든 데이터 모양 (docs/QUIZ.md 기준).

ParsedDocument = 팀원 파서 산출물의 내부 모델. 입력 형식(md/JSON)이 무엇이든
어댑터가 이 모양으로 변환하고, 파이프라인 전체는 이것만 바라본다.
"""
from typing import Literal

from pydantic import BaseModel, Field

QuizType = Literal["mcq", "cloze", "shortAnswer", "trueFalse"]

# 원문 형태 → 유형 후보의 근거가 되는 분류 (docs/QUIZ.md §2-⑤ 표)
ContentForm = Literal["definition", "enumeration", "sequence", "contrast"]

FORM_TYPE_CANDIDATES: dict[ContentForm, list[QuizType]] = {
    "definition": ["shortAnswer", "mcq", "trueFalse"],
    "enumeration": ["mcq"],
    "sequence": ["cloze"],
    "contrast": ["trueFalse", "mcq"],
}


# ── 내부 모델: ParsedDocument ──────────────────────────────


class SentenceAnchor(BaseModel):
    start: int  # 조각 raw_text 기준 문자 offset [start, end)
    end: int


class ParsedFigure(BaseModel):
    page: int
    offset: int  # raw_text 내 위치
    kind: str  # 'figure' | 'chart'
    needs_vision: bool  # True면 텍스트만으로 불완전 → 주변 문장 출제 제외


class ParsedConcept(BaseModel):
    name: str
    definition: str = ""
    prereqs: list[str] = Field(default_factory=list)


class ParsedChunk(BaseModel):
    index: int
    page_from: int
    page_to: int
    raw_text: str
    sentences: list[SentenceAnchor] = Field(default_factory=list)
    concepts: list[ParsedConcept] = Field(default_factory=list)
    figures: list[ParsedFigure] = Field(default_factory=list)


class ParsedToc(BaseModel):
    index: int
    title: str
    chunk_indexes: list[int] = Field(default_factory=list)


class ParsedDocument(BaseModel):
    parser_version: str
    source_name: str = ""
    tocs: list[ParsedToc]
    chunks: list[ParsedChunk]


class ParseReport(BaseModel):
    """수신 검증 결과 — 이상 시 팀원에게 그대로 전달 가능한 형태."""

    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


# ── 설정 ──────────────────────────────────────────────────


class QuizGenConfig(BaseModel):
    """전부 조정 가능. 기출 스타일 프로파일이 있으면 type_ratio를 override."""

    type_ratio: dict[QuizType, float] = {
        "mcq": 0.4,
        "cloze": 0.25,
        "shortAnswer": 0.25,
        "trueFalse": 0.1,
    }
    per_concept_min: int = 1  # 커버리지 바닥
    per_concept_max: int = 3  # 중요 개념 상한
    toc_multiplier: float = 1.5  # 목차 예산 = clamp(개념수 × 계수, min, max)
    toc_min: int = 15
    toc_max: int = 80
    overgen_ratio: float = 1.15  # 검증 탈락 대비 과생성
    # None = 모든 파서 버전 허용(기본). 특정 버전만 받으려면 리스트로 지정.
    supported_parser_versions: list[str] | None = None


# ── 계획 (선별·예산의 산출물, 생성 콜의 입력) ──────────────


class ConceptPlan(BaseModel):
    """개념 하나에 대한 출제 계획."""

    name: str
    definition: str
    form: ContentForm
    types: list[QuizType]  # 실제 생성할 유형들 (예산·배분이 확정)
    evidence_sentence_ids: list[int]  # 이 개념의 근거 후보 문장 (조각 내 인덱스)


class ChunkWorkOrder(BaseModel):
    """조각 하나 = LLM 생성 호출 하나의 작업 지시."""

    toc_index: int
    chunk_index: int
    concept_plans: list[ConceptPlan]


# ── 생성 결과 ─────────────────────────────────────────────


class GeneratedItem(BaseModel):
    """LLM 생성 콜의 출력 스키마 (문항 1개). evidence는 문장 번호로 받는다."""

    type: QuizType
    concept: str
    data: dict  # type별 알맹이 (mcq: question/options/answerIndex/…)
    evidence_sentence_ids: list[int]
    difficulty: int = Field(default=2, ge=1, le=5)


class QuizItemOut(BaseModel):
    """저장/서빙용 최종 문항. evidence는 offset + 원문 슬라이스로 변환 완료."""

    course_id: str
    document_id: str
    toc_index: int
    type: QuizType
    concept_name: str
    data: dict
    evidence: dict  # {chunkIndex, sentenceRanges[[s,e]], text, pageFrom, pageTo}
    difficulty: int
    verified: bool


# ── 서빙 API DTO ──────────────────────────────────────────


class TocSummary(BaseModel):
    toc_index: int
    title: str
    item_count: int


class QuizBankSummary(BaseModel):
    course_id: str
    document_id: str
    tocs: list[TocSummary]
    total: int


class SessionRequest(BaseModel):
    document_id: str
    toc_indexes: list[int]
    count: int = Field(default=10, ge=1, le=50)


class SessionItem(BaseModel):
    """정답·해설을 제거한 출제용 문항 (serving.strip_answers 산출)."""

    id: str
    toc_index: int
    type: QuizType
    data: dict


class SessionResponse(BaseModel):
    items: list[SessionItem]


class AttemptRequest(BaseModel):
    quiz_item_id: str
    user_input: str | int | bool | list[str]


class AttemptResponse(BaseModel):
    correct: bool
    answer: dict  # 정답 표시용 (type별 모양)
    explanation: str | None = None  # 고른 선지 기준 해설 (mcq)
    evidence: dict  # 근거 원문 + 페이지
