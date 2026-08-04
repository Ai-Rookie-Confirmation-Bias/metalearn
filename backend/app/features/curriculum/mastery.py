"""[순수로직] 학습 상태 — 절별 숙련도와 목차별 집계.

DB·LLM 비의존. **커리큘럼이 바뀌려면 바꿀 근거가 있어야 하고, 그 근거가 여기다.**

## 왜 절 단위인가

개념 단위로 숙련도를 매기려면 개념마다 문항이 3~4개는 있어야 한다. 실측에서
개념이 377~527개였으니 문항이 1,500개 넘게 필요하다. 절(103~135개)로 매기면
절당 3~5문항, 총 300~500문항으로 관리된다. 그리고 절이 곧 학습 단위이자 화면
단위라 "이 절을 얼마나 아는가"가 사용자에게도 자연스럽다.

개념별 약점은 따로 센다 — 어느 절이 약한지는 절로, 그 안에서 **무엇이** 약한지는
개념으로 봐야 다음 목차 설명에 녹일 대상을 고를 수 있다.

## 왜 시도 횟수가 필요한가

1문제 맞혔다고 "확실히 안다"고 하면 안 된다. 성향 프로파일에서 confidence로
판단을 미룬 것과 같은 원리다 — **측정이 부족하면 판정하지 않는다.**
`MIN_ATTEMPTS` 미만이면 정답률과 무관하게 '학습 중'으로 둔다.

## 왜 최근 결과를 따로 보는가

처음엔 틀리다가 나중에 맞히면 **배운 것**이다. 누적 정답률만 보면 초반 오답이
영원히 발목을 잡아 "나아졌다"를 보여줄 수 없다. 화면의 `↗ 나아짐` 표시가
이 값에서 나온다.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# 이보다 적게 풀었으면 정답률을 믿지 않는다.
MIN_ATTEMPTS = 3
# 최근 몇 개를 추세 판단에 쓰는가.
RECENT_WINDOW = 5
# 이 횟수 이상 틀린 개념은 "약점"으로 본다 — 한 번은 실수일 수 있다.
WEAK_THRESHOLD = 2

SOLID = 0.8  # 이 이상이면 확실
SHAKY = 0.5  # 이 아래면 약함

# 상태 라벨 — 화면에 그대로 쓴다.
UNTOUCHED = "untouched"  # 아직 안 함
LEARNING = "learning"  # 학습 중(판정 보류)
WEAK = "weak"  # 약함
SHAKY_S = "shaky"  # 흔들림
SOLID_S = "solid"  # 확실


@dataclass
class SectionMastery:
    """절 하나의 학습 상태."""

    section_id: str
    attempts: int = 0
    correct: int = 0
    # 최근 결과(True=정답). 앞이 오래된 것.
    recent: list[bool] = field(default_factory=list)
    # 개념별 오답 횟수 — 다음 목차 설명에 녹일 대상을 고르는 근거.
    wrong_by_concept: dict[str, int] = field(default_factory=dict)

    @property
    def ratio(self) -> float:
        return self.correct / self.attempts if self.attempts else 0.0

    @property
    def status(self) -> str:
        if self.attempts == 0:
            return UNTOUCHED
        if self.attempts < MIN_ATTEMPTS:
            return LEARNING  # 판정하기엔 너무 적다
        if self.ratio >= SOLID:
            return SOLID_S
        if self.ratio >= SHAKY:
            return SHAKY_S
        return WEAK

    @property
    def improving(self) -> bool:
        """최근에 나아지고 있는가 — 화면의 `↗ 나아짐` 표시.

        누적 정답률은 낮은데 최근이 좋으면 배우고 있는 중이다.
        """
        if len(self.recent) < 3 or self.ratio >= SOLID:
            return False
        tail = self.recent[-3:]
        return all(tail)

    @property
    def weak_concepts(self) -> tuple[str, ...]:
        """두 번 이상 틀린 개념. 많이 틀린 순."""
        items = [(k, n) for k, n in self.wrong_by_concept.items() if n >= WEAK_THRESHOLD]
        items.sort(key=lambda t: (-t[1], t[0]))
        return tuple(k for k, _ in items)


def record(
    state: SectionMastery, correct: bool, concept_key: str | None = None
) -> SectionMastery:
    """인출 하나의 결과를 반영한다(새 객체 반환 — 원본 불변)."""
    recent = (state.recent + [correct])[-RECENT_WINDOW:]
    wrong = dict(state.wrong_by_concept)
    if not correct and concept_key:
        wrong[concept_key] = wrong.get(concept_key, 0) + 1
    return SectionMastery(
        section_id=state.section_id,
        attempts=state.attempts + 1,
        correct=state.correct + (1 if correct else 0),
        recent=recent,
        wrong_by_concept=wrong,
    )


@dataclass(frozen=True)
class ChapterMastery:
    """목차 하나의 집계 — Rule Engine(분량 배분)의 입력."""

    chapter: str
    sections_total: int
    sections_touched: int
    ratio: float  # 시도한 절들의 가중 정답률
    weak_concepts: tuple[str, ...]
    attempts: int = 0  # 이 목차에서 푼 문항 수 — **판정할 자격이 있는지**를 본다

    @property
    def progress(self) -> float:
        """진도율 — 이해도와 다르다. 얼마나 훑었는가."""
        return self.sections_touched / self.sections_total if self.sections_total else 0.0

    @property
    def judged(self) -> bool:
        """이해도를 말할 만큼 풀었는가.

        절에 `MIN_ATTEMPTS` 가드를 걸어놓고 목차엔 안 걸었더니, **한 문제 틀리면
        단원 전체가 "이해도 0%로 낮아 설명을 늘렸습니다"로 뒤집혔다**(실측).
        한 문제로 이해도를 말하는 건 거짓말이다 — 성향에 confidence를 둔 것과
        같은 원리로, **측정이 부족하면 판정하지 않는다.**
        """
        return self.attempts >= MIN_ATTEMPTS

    @property
    def status(self) -> str:
        if self.sections_touched == 0:
            return UNTOUCHED
        if not self.judged:
            return LEARNING  # 아직 판정하기엔 이르다
        if self.ratio >= SOLID:
            return SOLID_S
        if self.ratio >= SHAKY:
            return SHAKY_S
        return WEAK


def chapter_summary(chapter: str, states: list[SectionMastery]) -> ChapterMastery:
    """절 상태들을 목차 단위로 묶는다.

    이해도는 **시도한 절만**으로 낸다. 안 푼 절을 0점으로 세면 진도가 곧
    이해도가 되어, "많이 봤지만 잘 모른다"와 "조금 봤지만 잘 안다"를 구분할 수
    없다. 진도는 progress로 따로 본다.

    가중은 시도 횟수로 한다 — 3문제 푼 절과 10문제 푼 절을 같은 무게로 평균내면
    적게 푼 절의 흔들림이 과대 반영된다.
    """
    touched = [s for s in states if s.attempts > 0]
    total_attempts = sum(s.attempts for s in touched)
    ratio = (
        sum(s.correct for s in touched) / total_attempts if total_attempts else 0.0
    )

    # 절을 넘나들며 반복해서 틀린 개념을 모은다.
    counter: dict[str, int] = {}
    for s in touched:
        for key, n in s.wrong_by_concept.items():
            counter[key] = counter.get(key, 0) + n
    weak = sorted(
        (k for k, n in counter.items() if n >= WEAK_THRESHOLD),
        key=lambda k: (-counter[k], k),
    )

    return ChapterMastery(
        chapter=chapter,
        sections_total=len(states),
        sections_touched=len(touched),
        ratio=round(ratio, 3),
        weak_concepts=tuple(weak),
        attempts=total_attempts,
    )


@dataclass(frozen=True)
class CourseMastery:
    """과목 전체 — **서비스가 끝나는 지점**을 정의한다.

    끝이 없으면 "이제 됐다"를 줄 수 없다. 일반 퀴즈 앱이 "15문제 중 9정답"에서
    멈추는 것과 갈리는 지점이 여기다.
    """

    chapters: tuple[ChapterMastery, ...]

    @property
    def readiness(self) -> float:
        """준비도 — 목차 이해도를 **절 수로 가중**한 평균.

        절 수로 가중하는 이유: 절 26개짜리 목차와 16개짜리 목차를 같은 무게로
        평균내면 작은 목차 하나가 전체를 흔든다. 분량이 곧 비중이다.
        안 본 목차는 0으로 센다 — 여기서는 **진도까지 포함한 값**이어야
        "시험 준비 완료"가 의미를 갖는다(이해도만 보면 한 목차만 풀고 100%가 된다).
        """
        total = sum(c.sections_total for c in self.chapters)
        if not total:
            return 0.0
        weighted = sum(c.ratio * c.progress * c.sections_total for c in self.chapters)
        return round(weighted / total, 3)

    @property
    def complete(self) -> bool:
        """완료 판정 — 전 목차가 기준 이상. Bloom의 Mastery Learning에서 온 선."""
        return bool(self.chapters) and all(
            c.ratio >= SOLID and c.progress >= 1.0 for c in self.chapters
        )

    @property
    def weakest(self) -> ChapterMastery | None:
        """가장 약한 목차 — 화면의 🔴 표시. 안 본 목차는 제외한다."""
        touched = [c for c in self.chapters if c.sections_touched]
        return min(touched, key=lambda c: c.ratio) if touched else None

    @property
    def remaining_sections(self) -> int:
        return sum(c.sections_total - c.sections_touched for c in self.chapters)

    def estimated_minutes(self, per_section: int = 8) -> int:
        """남은 시간 추정. per_section은 실측 전까지 추정값이다."""
        return self.remaining_sections * per_section


def course_summary(chapters: list[ChapterMastery]) -> CourseMastery:
    return CourseMastery(chapters=tuple(chapters))


def label(status: str) -> str:
    """화면에 쓸 한국어. 코드 값과 표시를 한 곳에서 묶어 둔다."""
    return {
        UNTOUCHED: "아직 안 함",
        LEARNING: "학습 중",
        WEAK: "약함",
        SHAKY_S: "흔들림",
        SOLID_S: "확실",
    }.get(status, status)
