"""[2.DTO] 문제 생성 에이전트 입출력 계약.

입력 = 파싱 에이전트 → 생성 에이전트 (개념 구간 + 원문).
출력 = 생성 에이전트 → 검증 에이전트 / DB (문항 + 근거).
"""
from enum import IntEnum, StrEnum

from pydantic import BaseModel, Field, model_validator


class Level(IntEnum):
    """블룸 단계 축약 — L1 암기 / L2 적용 / L3 심화."""

    RECALL = 1
    APPLY = 2
    DEEP = 3


class ProblemType(StrEnum):
    """문항 유형 — 모두 **서버가 규칙으로 채점 가능한** 형태만 둔다.

    문제은행이 한 가지 유형뿐이면 20문제만 풀어도 지겹고, 추측으로 뚫린다.
    유형마다 정답의 자료형이 다르므로(str / list) answer를 유니온으로 두고
    타입별 규칙은 Problem.validate에서 검사한다.
    """

    MCQ = "mcq"  # 4지선다 — 정답 1개
    MULTI = "multi"  # 다중 정답 — "모두 고르시오". 추측이 어렵다
    OX = "ox"  # 참/거짓 — 단독으론 약하나(추측률 50%) 개념 확인에 빠르다
    ORDER = "order"  # 순서 배열 — 절차·단계가 있는 원문에서만 성립


# 유형별 정답 자료형: str 하나 / 문자열 목록
Answer = str | list[str]


class Distractor(BaseModel):
    """오답 보기 하나와, 그것을 고르는 이유.

    두 가지를 한꺼번에 해결한다.

    ① **오답 화면의 데이터** — 학습자가 틀렸을 때 "왜 그 답을 골랐는지"를
       그 자리에서 보여준다. 푸는 시점에 LLM으로 추론하면 느리고 흔들리므로
       생성 시점에 미리 만들어 둔다.
    ② **오답 품질** — 실측에서 mcq 7문항 중 3문항이 "정답만 원문에 있고 오답은
       전부 창작"이었다. 원문을 한 번 본 사람은 읽어본 문장 하나만 고르면 된다.
       `confused_with`를 원문에서 가져오게 강제하면 이 결함이 구조적으로 막힌다.
    """

    text: str  # options 중 하나 (정답이 아닌 것)
    # 원문의 **어느 항목과** 헷갈리게 만든 것인지. 원문 실재 검사 대상이다.
    confused_with: str
    # 학습자에게 보여줄 한 줄 — 정답과 무엇이 갈리는지.
    note: str


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
    # 레벨별 목표 문항 수. 레벨 게이트(정답률 80%)가 의미를 가지려면 실제로는
    # 10~15가 필요하다 — 5문항이면 1개만 틀려도 통과가 무너진다.
    per_level: int = Field(default=2, ge=1, le=20)


# ── 출력 계약 (생성 → 검증/DB) ──────────────────────────────────────
class Problem(BaseModel):
    level: Level
    type: ProblemType = ProblemType.MCQ
    question: str
    # ox는 보기가 없다(정답이 O/X 고정). 나머지 유형은 아래 검증에서 개수를 본다.
    options: list[str] = Field(default_factory=list)
    # 정답 자료형이 유형마다 다르다 — mcq/ox는 문자열, multi/order는 문자열 목록.
    # 보기 원문과 글자까지 일치해야 한다(서빙 시 스트립·채점 대조 기준).
    answer: Answer
    explanation: str
    # ★ 검증 에이전트 v1의 입력 — 원문에 실재하는 근거 문구.
    source_evidence: str
    # 오답 화면의 재료. 지금은 **선택**이다 — 필수로 걸면 이것 하나 빠졌다고
    # 멀쩡한 문항이 폐기되어 수율이 무너진다. 실측으로 산출률을 본 뒤 강화한다.
    distractors: list[Distractor] = Field(default_factory=list)

    @property
    def answer_texts(self) -> list[str]:
        """정답을 항상 목록으로 — 게이트들이 유형에 상관없이 다룰 수 있게."""
        return list(self.answer) if isinstance(self.answer, list) else [self.answer]

    @model_validator(mode="after")
    def _check_by_type(self) -> "Problem":
        """유형별 규칙 검사.

        LLM이 라벨("C")로 답하거나, 다중정답인데 하나만 주거나, 순서 배열인데
        보기 일부만 나열하는 사고가 실제로 잦다. 형식 단계에서 확정 차단한다.
        """
        opts, ans = self.options, self.answer

        if self.type is ProblemType.OX:
            if not isinstance(ans, str) or ans not in ("O", "X"):
                raise ValueError("ox 문항의 answer는 'O' 또는 'X'여야 한다")
            # 보기를 채워 보내와도 무의미하므로 버린다(화면은 O/X 고정 렌더).
            object.__setattr__(self, "options", [])
            return self

        if len(opts) < 2:
            raise ValueError(f"{self.type} 문항은 보기가 2개 이상이어야 한다")
        if len(set(opts)) != len(opts):
            raise ValueError("보기에 중복이 있다")

        if self.type is ProblemType.MCQ:
            if not isinstance(ans, str):
                raise ValueError("mcq 문항의 answer는 문자열 1개여야 한다")
            if ans not in opts:
                raise ValueError(f"answer '{ans}'가 보기에 없다")
            return self

        if not isinstance(ans, list):
            raise ValueError(f"{self.type} 문항의 answer는 목록이어야 한다")
        missing = [a for a in ans if a not in opts]
        if missing:
            raise ValueError(f"answer 항목이 보기에 없다: {missing}")

        if self.type is ProblemType.MULTI:
            # 정답이 1개면 mcq이고, 전부면 고를 것이 없다 — 둘 다 결함 문항이다.
            if not 2 <= len(ans) < len(opts):
                raise ValueError("multi 문항의 정답은 2개 이상, 보기 전체 미만이어야 한다")
            if len(set(ans)) != len(ans):
                raise ValueError("multi 문항의 정답에 중복이 있다")
        else:  # ORDER — 보기 전체를 빠짐없이 한 번씩 배열해야 한다
            if sorted(ans) != sorted(opts):
                raise ValueError("order 문항의 answer는 보기 전체의 순열이어야 한다")
        return self

    @model_validator(mode="after")
    def _clean_distractors(self) -> "Problem":
        """오답 메모를 정리한다 — 깨진 항목은 **문항을 죽이지 않고 버린다.**

        보기에 없는 텍스트를 적거나 정답을 오답이라고 적는 사고가 난다.
        그렇다고 문항 전체를 폐기하면 부가 정보 하나 때문에 본체를 잃는다.
        (`_check_by_type` 다음에 돌므로 ox의 options는 이미 비워져 있다.)
        """
        if self.type is ProblemType.OX or not self.distractors:
            object.__setattr__(self, "distractors", [])
            return self
        answers = set(self.answer_texts)
        kept: list[Distractor] = []
        seen: set[str] = set()
        for d in self.distractors:
            if d.text in self.options and d.text not in answers and d.text not in seen:
                seen.add(d.text)
                kept.append(d)
        object.__setattr__(self, "distractors", kept)
        return self


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
