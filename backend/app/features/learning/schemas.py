"""[2.DTO] 블록 봉투 계약 (기획서 §5 / §7).

모든 콘텐츠는 동일한 JSON 봉투로 흐른다:
  { id, type, conceptId, source, sourceChunkIds, externalRefs, verified, data, meta }

- 프론트는 `type`으로 렌더러를 고르고 `data`만 채운다(컴포넌트가 HTML을 만들지 않음).
- 서버가 생성·검증·채점의 진실. `verified=true`인 봉투만 서빙된다.
- 와이어(JSON)는 camelCase. 내부 파이썬은 snake_case로 쓰고 alias로 직렬화한다.
- `data`는 type별로 모양이 다르다. 1차 5종(concept/cloze/mcq/explainBack/reviewGate)은
  아래 타입 모델로 검증하고, 그 외 확장 type은 자유 dict로 흐른다.
"""
from __future__ import annotations

import uuid
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationInfo,
    field_validator,
    model_validator,
)


def _to_camel(s: str) -> str:
    head, *rest = s.split("_")
    return head + "".join(w.capitalize() for w in rest)


class _CamelModel(BaseModel):
    """camelCase 직렬화 + snake_case/camelCase 양쪽 입력 허용 공통 베이스."""

    model_config = ConfigDict(alias_generator=_to_camel, populate_by_name=True)


# ── 출처 / 메타 ──────────────────────────────────────────────────────────────
BlockSource = Literal["book", "ai_prereq", "analogy"]
AttemptKind = Literal["diagnostic", "learn", "review", "connection"]
Difficulty = Literal["easy", "mid", "hard"]


class ExternalRefOut(_CamelModel):
    """ai_prereq 블록의 외부 근거 인용(🤖 배지로 렌더)."""

    title: str | None = None
    url: str | None = None
    kind: str | None = None  # web | corpus | prereq_db


class BlockMeta(_CamelModel):
    difficulty: Difficulty = "mid"
    version: int = 1
    # 복습 블록의 이유 라벨(변화 가시성, SERVICE_OVERVIEW §4) — 이 카드가 왜
    # 나왔는지("5일 전 배운 개념, 잊힐 때가 됐어요"). 생성 시 스탬프, 복습 전용.
    review_reason: str | None = None


# ── type별 data 모델 (1차 5종) ───────────────────────────────────────────────
class ConceptData(_CamelModel):
    """① 설명 블록. 추적 없음. 왜 배우나(앞연결) 한 줄 포함 가능.

    구조화 필드(example/misconception)는 '텍스트 벽' 해소용 — 프론트가 각각
    색·아이콘이 다른 박스로 렌더한다(HTML 생성 금지 원칙: 구조는 JSON, 그림은 렌더러).
    """

    title: str
    body: str
    why_it_matters: str | None = None
    example: str | None = None  # 구체 예시 1개(근거 범위 안)
    misconception: str | None = None  # 흔한 오해/헷갈리는 지점 경고


class AnalogyData(_CamelModel):
    """① 비유 블록. 검증 면제, '사실 아님' 라벨 강제."""

    label: Literal["비유"] = "비유"
    text: str


class ImageData(_CamelModel):
    """① 교재 그림 블록(Layer 2). 추적 없음. LLM 생성이 아니라 서버가
    doc_figures(원문 크롭)를 절 근거 페이지와 매칭해 붙인다 — 환각 0.
    프론트는 figureId로 GET /api/documents/figures/:id를 <img src>에 문다.
    """

    figure_id: str
    page: int | None = None
    caption: str | None = None


class TableData(_CamelModel):
    """① 비교표 블록. 추적 없음. LAN/WAN, OSI 계층처럼 나열·비교가
    문단보다 나은 개념용 — LLM은 {columns, rows} JSON만 뽑고 표는 렌더러가 그린다.
    """

    title: str | None = None
    columns: list[str] = Field(min_length=2)
    rows: list[list[str]] = Field(min_length=1)
    caption: str | None = None  # 표 아래 한 줄 부연(선택)

    @field_validator("rows", mode="after")
    @classmethod
    def _align_rows(cls, rows: list[list[str]], info: ValidationInfo) -> list[list[str]]:
        """행 길이를 열 수에 맞춘다(초과 절단·부족 공백) — LLM 정렬 실수에 관대."""
        cols = info.data.get("columns")
        if not cols:
            return rows
        width = len(cols)
        return [([str(c) for c in r] + [""] * width)[:width] for r in rows]


class DiagramNode(_CamelModel):
    id: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_]{0,15}$")
    label: str = Field(min_length=1, max_length=40)


class DiagramEdge(_CamelModel):
    source: str  # 노드 id 참조
    target: str
    label: str | None = Field(default=None, max_length=20)

    @field_validator("label", mode="before")
    @classmethod
    def _empty_to_none(cls, v: object) -> object:
        return None if isinstance(v, str) and not v.strip() else v


class DiagramData(_CamelModel):
    """① 다이어그램 블록. 추적 없음. v1은 flowchart만(절차·구조·포함 관계).

    LLM은 그래프 JSON(nodes/edges)만 만들고 Mermaid 코드는 서버가 결정적으로
    조립한다(diagram.assemble_mermaid) → 문법 오류가 구조적으로 불가능.
    그래프 정합성 검증(렌더 가능성 게이트)은 여기 검증기가 담당:
    치명 결함(dangling 참조·id 중복)은 폐기, 사소한 결함(자기 루프·고립 노드)은
    제거 후 통과 — table의 행 패딩과 같은 관대 처리 철학.
    조립된 `mermaid` 문자열은 모델 밖에서 주입된다(LLM이 넣어도 무시됨).
    """

    title: str
    direction: Literal["TD", "LR"] = "TD"
    nodes: list[DiagramNode] = Field(min_length=2, max_length=8)
    edges: list[DiagramEdge] = Field(min_length=1, max_length=12)
    caption: str | None = None  # 한 줄 설명(선택)

    @model_validator(mode="after")
    def _validate_graph(self) -> "DiagramData":
        ids = [n.id for n in self.nodes]
        idset = set(ids)
        if len(ids) != len(idset):
            raise ValueError("노드 id 중복")
        if any(e.source not in idset or e.target not in idset for e in self.edges):
            raise ValueError("edge가 없는 노드를 참조(dangling)")
        # 자기 루프(A→A)는 엣지만 제거하고 통과 — 전부 사라지면 폐기
        edges = [e for e in self.edges if e.source != e.target]
        if not edges:
            raise ValueError("유효한 edge 없음")
        # 고립 노드(어느 엣지에도 안 붙음)는 제거하고 통과 — 2개 미만이 되면 폐기
        used = {e.source for e in edges} | {e.target for e in edges}
        nodes = [n for n in self.nodes if n.id in used]
        if len(nodes) < 2:
            raise ValueError("연결된 노드가 2개 미만")
        self.edges = edges
        self.nodes = nodes
        return self


class ClozeData(_CamelModel):
    """② 빈칸 블록. text의 {{}} 위치에 blanks가 순서대로 대응."""

    text: str
    blanks: list[str]
    hint: str | None = None


class McqData(_CamelModel):
    """② 객관식 블록. answerIndex는 서버 채점용(서빙 시 제외 가능)."""

    question: str
    options: list[str]
    answer_index: int | None = None
    explanation: str | None = None


class ExplainBackData(_CamelModel):
    """② 서술형 블록. rubric 키포인트로 서버가 0~1 채점."""

    prompt: str
    rubric: list[str] = Field(default_factory=list)


class ReviewGateData(_CamelModel):
    """③ 복습 게이트. 통과해야 다음 진행."""

    prompt: str
    rubric: list[str] = Field(default_factory=list)


# ── 봉투 ─────────────────────────────────────────────────────────────────────
class BlockEnvelope(_CamelModel):
    """백엔드 → 프론트: 콘텐츠 블록 1개(공통 봉투)."""

    id: str
    type: str
    # diagnostic | learn | review | connection — attempts.kind로 그대로 방출(프론트 registry)
    kind: str | None = None
    concept_id: str | None = None
    source: BlockSource = "book"
    source_chunk_ids: list[str] = Field(default_factory=list)
    external_refs: list[ExternalRefOut] = Field(default_factory=list)
    verified: bool = False
    tracked: bool = False
    data: dict = Field(default_factory=dict)
    meta: BlockMeta = Field(default_factory=BlockMeta)


class SectionBlocksResponse(_CamelModel):
    """GET /sections/:id → 절의 검증된 봉투 배열.

    프론트 SectionPayload 계약: id/title/blocks. sectionId·conceptId·variant는 부가.
    """

    id: str
    title: str = ""
    section_id: str
    concept_id: str | None = None
    variant: Literal["full", "compressed", "quick"] = "full"
    blocks: list[BlockEnvelope] = Field(default_factory=list)


# ── 정답 기록 (§7) ───────────────────────────────────────────────────────────
class AttemptRequest(_CamelModel):
    """프론트 → 백엔드: onAnswer({blockId, conceptId, userInput}).

    correct는 받아도 무시한다 — 정오 판정은 서버만 한다(정답은 서빙 시 스트립됨).
    meta: 프론트 신호 통로(elapsedMs 체류시간, hintsUsed 등) → attempts.meta에 병합.
    """

    block_id: str | None = None
    concept_id: str
    kind: AttemptKind = "learn"
    type: str | None = None
    correct: bool | None = None  # (무시됨 — 하위호환용 필드)
    user_input: str | dict | int | list | None = None
    meta: dict | None = None


class ConceptStateOut(_CamelModel):
    concept_id: str
    strength: float
    status: str  # locked | todo | learning | mastered
    explanation_score: float = 0.0
    next_due_at: str | None = None


class AttemptFeedback(_CamelModel):
    missed_points: list[str] = Field(default_factory=list)
    comment: str = ""


class NextActionOut(_CamelModel):
    """채점 직후 다음 행동(살아있는 커리큘럼 신호, next_action.py).

    advance | thin_pass | supplement | prerequisite
    """

    action: str
    reason: str


class CauseOut(_CamelModel):
    """원인 국소화 결과(ISSUE-010): 왜 틀렸나.

    type: hold(판단보류) | prerequisite(선수결손) | content(본문결손)
          | misconception(오개념) | ok(충분)
    blameConceptId: prerequisite일 때 보충 대상 선행 개념(최상류 약한 선행).
    """

    type: str
    reason: str
    blame_concept_id: str | None = None


class PrerequisiteTargetOut(_CamelModel):
    """cause=prerequisite → 삽입/라우팅할 선행 학습 지점(살아있는 커리큘럼, ISSUE-002).

    created=true면 이번에 새로 끼운 prereq 챕터, false면 기존 절 재사용(멱등).
    프론트는 이 chapterId로 생성 트리거(POST /chapters/:id/generate) 후 sectionId를
    학습시키고, 끝나면 원래 절로 복귀한다(복귀는 프론트 책임).
    """

    concept_id: str
    chapter_id: str
    section_id: str
    title: str
    gen_status: str
    created: bool = False


class RevealOut(_CamelModel):
    """채점 **후** 공개하는 정답/해설. 서빙 시엔 스트립되지만 답한 뒤엔 유출 아님.

    프론트가 "정답은 B · 해설은…"을 라운드트립으로 표시하는 데 쓴다(클라 answerIndex 대체).
    """

    answer_index: int | None = None  # mcq 정답 인덱스
    blanks: list[str] | None = None  # cloze 정답들(순서대로)
    blank_results: list[bool] | None = None  # cloze 빈칸별 정오(순서대로, 서버 판정)
    explanation: str | None = None   # mcq 해설 / cloze 힌트(왜 정답인지)


class AttemptResponse(_CamelModel):
    """정답 기록 결과. explainBack이면 score/feedback 포함."""

    correct: bool | None = None
    score: float | None = None
    feedback: AttemptFeedback | None = None
    reveal: RevealOut | None = None
    concept: ConceptStateOut
    next_action: NextActionOut | None = None
    cause: CauseOut | None = None
    prerequisite: PrerequisiteTargetOut | None = None
    # 이 절을 완료해 복귀할 지점(선행 끝냄 → 원래 절). 없으면 null.
    resume_section_id: str | None = None


class SupplementResponse(_CamelModel):
    """POST /blocks/:id/supplement — 오답 맞춤 보충(재설명). 개입 사다리 ②(ISSUE-005).

    학습자의 실제 오답을 입력으로 '무엇을 놓쳤나'(diagnosis)와 그 오해를 겨냥한
    재설명을 생성한다. 개인화 콘텐츠라 blocks에 영속하지 않는다(blocks는 유저 무관
    테이블 — 넣으면 다른 학습자에게 유출). fallback=true면 LLM 실패로 근거 인용만.
    """

    block_id: str
    concept_id: str
    diagnosis: str
    misconception: bool = False
    title: str
    body: str
    fallback: bool = False


class TutorChatTurn(_CamelModel):
    role: Literal["user", "tutor"]
    text: str = Field(min_length=1, max_length=1000)


class TutorChatRequest(_CamelModel):
    """POST /tutor/chat — 현재 절 컨텍스트의 근거 접지 Q&A.

    history는 프론트가 들고 있는 이번 절의 최근 대화(서버 무저장 — 개인화
    콘텐츠는 영속하지 않는 supplement와 동일 원칙).
    """

    section_id: str
    message: str = Field(min_length=1, max_length=500)
    history: list[TutorChatTurn] = Field(default_factory=list, max_length=12)


class TutorChatResponse(_CamelModel):
    """튜터 응답. 정답 비유출(소크라틱) 규칙은 서버 프롬프트가 강제."""

    section_id: str
    reply: str


class OfflinePackBlock(_CamelModel):
    """오프라인 팩 블록 1개 — **정답 포함 원본 data**(스트립 안 함).

    소비자는 브라우저 UI가 아니라 사용자 기기의 로컬 엔진 어댑터(ondevice/)다:
    온라인일 때 미리 받아 두고, 오프라인이 되면 어댑터가 로컬 sLLM으로 채점을
    이어받는다(제안서 차별점 ④ 클라우드+로컬 이중구조).
    """

    id: str
    type: str
    concept_id: str | None = None
    tracked: bool = False
    data: dict = Field(default_factory=dict)


class OfflinePackResponse(_CamelModel):
    """GET /sections/:id/offline-pack — 절 1개의 오프라인 채점 팩."""

    section_id: str
    title: str
    concept_name: str | None = None
    blocks: list[OfflinePackBlock] = Field(default_factory=list)


class NoteSaveRequest(_CamelModel):
    """PUT /sections/:id/note — 요약 노트 저장(upsert). 빈 문자열 = 비우기."""

    content: str = Field(max_length=20000)


class NoteResponse(_CamelModel):
    """GET/PUT /sections/:id/note 응답. 노트 없으면 content=""·updatedAt=null."""

    section_id: str
    content: str = ""
    updated_at: str | None = None


class CursorResponse(_CamelModel):
    """GET /courses/:id/cursor — 현재 학습 위치 + 복귀 대기 깊이(살아있는 커리큘럼)."""

    course_id: str
    current_section_id: str | None = None
    return_depth: int = 0


class ReadCompleteResponse(_CamelModel):
    """POST /sections/:id/read-complete — tracked 0개 절의 열람 완료 결과.

    채점 대상 블록이 없는 절(예: analogy만 있는 선행 절)은 attempts 경로로 완료가
    불가능하므로, '다 읽었어요'를 서버가 완료로 판정·기록한다(판단은 서버).
    resumeSectionId: 이 완료로 복귀 스택이 pop됐으면 돌아갈 절(없으면 null).
    """

    section_id: str
    status: str = "completed"
    resume_section_id: str | None = None


# ── JIT 생성 트리거 / 폴링 (§5) ──────────────────────────────────────────────
class GenerateTriggerResponse(_CamelModel):
    """POST /chapters/:id/generate → 트리거 결과(멱등)."""

    chapter_id: str
    gen_status: str  # pending | generating | ready | failed


class ChapterStatusResponse(_CamelModel):
    """GET /chapters/:id → 생성 상태 폴링."""

    chapter_id: str
    title: str
    origin: str  # book | prereq
    gen_status: str
    section_ids: list[str] = Field(default_factory=list)


# ── 확신도 → variant (§6) ────────────────────────────────────────────────────
class ConfidenceRequest(_CamelModel):
    confidence: Literal["sure", "ambiguous", "unknown"]


class ConfidenceResponse(_CamelModel):
    section_id: str
    confidence: str
    variant: Literal["full", "compressed", "quick"]


# ── placement 시딩 (진단 종료 → 수준 체크 진입점) ─────────────────────────────
class PlacementResponse(_CamelModel):
    """진단으로 확정된 floor/ceiling 기준 concept_mastery 초기 시딩 결과.

    seeded = 이번에 새로 시딩된 개념 수, skipped = 이미 상태가 있어 보존한 수.
    mastered/todo/locked = 코스 전체 개념의 최종 배치 분포.
    """

    course_id: str
    floor_concept_id: str | None = None
    ceiling_concept_id: str | None = None
    seeded: int = 0
    skipped: int = 0
    mastered: int = 0
    todo: int = 0
    locked: int = 0
