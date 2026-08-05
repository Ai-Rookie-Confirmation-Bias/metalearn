"""[순수로직] 학습 상태 — 네 출처가 흘러드는 하나의 누적값.

DB·LLM 비의존. **커리큘럼이 바뀌려면 바꿀 근거가 있어야 하고, 그 근거가 여기다.**

## 하나로 누적한다

학습자가 문항을 푸는 자리는 넷이다. 넷을 따로 세면 "나는 지금 얼마나 준비됐나"에
답할 수 없다. 전부 같은 이벤트(`Attempt`)로 들어와 하나의 값으로 쌓인다.

    진단 평가   배우기 전. 어디서 시작할지 정한다
    인출 학습   절을 읽고 바로 꺼낸다 (지금 구현된 것)
    복습        시간이 지나고 다시 꺼낸다 (망각곡선)
    형성 평가   목차를 마치고 종합해서 묻는다

## 그런데 그냥 더하면 안 된다

한 문항이 담는 정보량이 출처마다 다르다.

    진단 0.5  배우기 전이라 **오답이 무지의 증거가 아니다.** 아직 안 배웠을
              뿐이다. 여기에 1.0을 주면 초반 오답이 영원히 발목을 잡아
              "나아졌다"를 못 보여준다.
    인출 1.0  기준. 방금 읽고 꺼낸 것
    복습 1.5  **시간이 지나고도 꺼냈다.** 방금 읽고 맞힌 것보다 훨씬 센 증거다
    형성 2.0  절을 넘나드는 종합 문항. 한 문항이 담는 범위가 넓다

## 망각은 숙련도를 깎지 않는다

시간이 지났다고 이해도를 떨어뜨리면, 아무것도 안 했는데 숫자가 내려간다.
화면에서 설명할 수 없고 학습자는 배신감을 느낀다. 그래서 둘로 나눈다.

    이해도(ratio)      얼마나 이해했나. **시간으로 안 떨어진다**
    회상 강도(recall)  지금 꺼낼 수 있나. 마지막 성공 이후 감쇠한다

복습이 필요한 절은 이해도가 낮은 절이 아니라 **회상 강도가 낮은 절**이다.
최종 준비도에서 둘을 곱한다 — 이해했고 지금 꺼낼 수 있어야 시험 준비가 된 것이다.

## 왜 절 단위인가

개념 단위로 숙련도를 매기려면 개념마다 문항이 3~4개는 있어야 한다. 실측에서
개념이 377~527개였으니 문항이 1,500개 넘게 필요하다. 절(103~135개)로 매기면
절당 3~5문항, 총 300~500문항으로 관리된다. 그리고 절이 곧 학습 단위이자 화면
단위라 "이 절을 얼마나 아는가"가 사용자에게도 자연스럽다.

개념별 약점은 따로 센다 — 어느 절이 약한지는 절로, 그 안에서 **무엇이** 약한지는
개념으로 봐야 다음 절·목차 설명에 녹일 대상을 고를 수 있다.

## 왜 측정량이 필요한가

1문제 맞혔다고 "확실히 안다"고 하면 안 된다. 성향 프로파일에서 confidence로
판단을 미룬 것과 같은 원리다 — **측정이 부족하면 판정하지 않는다.**
가중 시도량이 `MIN_WEIGHT` 미만이면 정답률과 무관하게 '학습 중'으로 둔다.

## 왜 최근 결과를 따로 보는가

처음엔 틀리다가 나중에 맞히면 **배운 것**이다. 누적 정답률만 보면 초반 오답이
영원히 발목을 잡아 "나아졌다"를 보여줄 수 없다. 화면의 `↗ 나아짐` 표시가
이 값에서 나온다.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

# ── 출처 ───────────────────────────────────────────────────────────

DIAGNOSTIC = "diagnostic"  # 진단 평가 — 배우기 전
RETRIEVAL = "retrieval"  # 인출 학습 — 절 안에서
REVIEW = "review"  # 복습 — 망각곡선을 타고 다시
FORMATIVE = "formative"  # 형성 평가 — 목차를 마치고

# 출처별 가중. 한 문항이 담는 정보량이 다르다(모듈 문서 참고).
WEIGHT: dict[str, float] = {
    DIAGNOSTIC: 0.5,
    RETRIEVAL: 1.0,
    REVIEW: 1.5,
    FORMATIVE: 2.0,
}

KIND_LABEL = {
    DIAGNOSTIC: "진단",
    RETRIEVAL: "학습",
    REVIEW: "복습",
    FORMATIVE: "평가",
}

# ── 기준선 ─────────────────────────────────────────────────────────

# 이만큼 안 쌓였으면 정답률을 믿지 않는다. 인출 3문제 = 3.0, 진단만이면 6문제.
MIN_WEIGHT = 3.0
# 최근 몇 개를 추세 판단에 쓰는가.
RECENT_WINDOW = 5
# 이 횟수 이상 틀린 개념은 "약점"으로 본다 — 한 번은 실수일 수 있다.
WEAK_THRESHOLD = 2

SOLID = 0.8  # 이 이상이면 확실
SHAKY = 0.5  # 이 아래면 약함

# 망각곡선. 처음 맞힌 직후의 반감기(일). 연속 성공마다 늘어난다 —
# 간격 반복(spaced repetition)의 핵심이다. 한 번 맞힌 것과 세 번 연속 맞힌 것을
# 같은 속도로 잊는다고 보면 복습이 끝없이 돌아온다.
BASE_HALF_LIFE_DAYS = 3.0
# 연속 성공 한 번마다 반감기가 이만큼 배가 된다. 상한을 둬서 무한히 안 늘어나게.
STREAK_FACTOR = 1.8
MAX_STREAK = 5
# 이 아래로 떨어지면 복습 대상.
REVIEW_THRESHOLD = 0.6

DAY = 86400.0

# 상태 라벨 — 화면에 그대로 쓴다.
UNTOUCHED = "untouched"  # 아직 안 함
LEARNING = "learning"  # 학습 중(판정 보류)
WEAK = "weak"  # 약함
SHAKY_S = "shaky"  # 흔들림
SOLID_S = "solid"  # 확실


@dataclass(frozen=True)
class Attempt:
    """문항 하나를 푼 결과. **네 출처가 전부 이 모양으로 들어온다.**

    출처를 안 들고 다니면 나중에 가중을 못 준다. 진단에서 틀린 것과 복습에서
    틀린 것은 전혀 다른 사건인데, 기록에 남지 않으면 구분할 방법이 없다.
    """

    kind: str
    correct: bool
    concept_key: str | None = None
    at: float = field(default_factory=time.time)

    @property
    def weight(self) -> float:
        return WEIGHT.get(self.kind, 1.0)


@dataclass
class SectionMastery:
    """절 하나의 학습 상태 — 네 출처의 누적."""

    section_id: str
    attempts: int = 0  # 푼 문항 수(가중 아님). 화면에 "3문제 풀었습니다"로 쓴다
    weight: float = 0.0  # 가중 시도량 — 판정 자격을 여기서 본다
    score: float = 0.0  # 가중 정답량
    # 출처별 문항 수. 화면에 "진단 2 · 학습 5 · 복습 1"로 쓴다.
    by_kind: dict[str, int] = field(default_factory=dict)
    # 최근 결과(True=정답). 앞이 오래된 것.
    recent: list[bool] = field(default_factory=list)
    # 개념별 오답 횟수 — 다음 절·목차 설명에 녹일 대상을 고르는 근거.
    wrong_by_concept: dict[str, int] = field(default_factory=dict)
    # 마지막으로 맞힌 시각. 망각곡선의 기준점.
    last_success: float | None = None
    # 연속 정답 수. 반감기를 늘리는 값 — 여러 번 맞힐수록 오래 간다.
    streak: int = 0

    @property
    def ratio(self) -> float:
        """이해도 — 가중 정답률. **시간으로 떨어지지 않는다.**"""
        return self.score / self.weight if self.weight else 0.0

    @property
    def judged(self) -> bool:
        """이해도를 말할 만큼 쌓였는가."""
        return self.weight >= MIN_WEIGHT

    @property
    def status(self) -> str:
        if self.attempts == 0:
            return UNTOUCHED
        if not self.judged:
            return LEARNING  # 판정하기엔 너무 적다
        if self.ratio >= SOLID:
            return SOLID_S
        if self.ratio >= SHAKY:
            return SHAKY_S
        return WEAK

    @property
    def half_life(self) -> float:
        """이 절의 반감기(초). 연속으로 맞힐수록 길어진다."""
        return BASE_HALF_LIFE_DAYS * DAY * (STREAK_FACTOR ** min(self.streak, MAX_STREAK))

    def recall(self, now: float | None = None) -> float:
        """회상 강도 — **지금 꺼낼 수 있는가**(0~1).

        마지막으로 맞힌 뒤 지난 시간으로 감쇠한다. 한 번도 못 맞혔으면 0이다.
        이해도와 따로 두는 이유는 모듈 문서를 보라 — 요약하면, 가만히 있는데
        이해도가 내려가면 화면에서 설명할 수 없다.
        """
        if self.last_success is None:
            return 0.0
        elapsed = max(0.0, (now if now is not None else time.time()) - self.last_success)
        return 2 ** (-elapsed / self.half_life)

    def needs_review(self, now: float | None = None) -> bool:
        """복습 대상인가. **이해도가 낮은 절이 아니라 잊혀가는 절이다.**

        ⚠️ 한 번도 못 맞힌 절은 복습이 아니다(실측 사고: 형성평가 오답 1건뿐인
        절이 "복습 대기"로 잡혔다). 그건 **아직 모르는 것**이라 처방이 다르다 —
        다시 꺼내보게 할 게 아니라 설명부터 다시 봐야 한다. 그쪽은 `status`가
        약함/학습 중으로 이미 잡는다.
        """
        return self.last_success is not None and self.recall(now) < REVIEW_THRESHOLD

    @property
    def improving(self) -> bool:
        """최근에 나아지고 있는가 — 화면의 `↗ 나아짐` 표시.

        누적 정답률은 낮은데 최근이 좋으면 배우고 있는 중이다.
        """
        if len(self.recent) < 3 or self.ratio >= SOLID:
            return False
        return all(self.recent[-3:])

    @property
    def weak_concepts(self) -> tuple[str, ...]:
        """두 번 이상 틀린 개념. 많이 틀린 순."""
        items = [(k, n) for k, n in self.wrong_by_concept.items() if n >= WEAK_THRESHOLD]
        items.sort(key=lambda t: (-t[1], t[0]))
        return tuple(k for k, _ in items)


def record(
    state: SectionMastery,
    correct: bool,
    concept_key: str | None = None,
    kind: str = RETRIEVAL,
    at: float | None = None,
) -> SectionMastery:
    """시도 하나를 반영한다(새 객체 반환 — 원본 불변).

    `kind` 기본값이 인출인 이유: 지금 화면에서 오는 건 전부 인출이다. 진단·복습·
    형성이 붙을 때 호출측이 명시하면 된다.
    """
    return apply(state, Attempt(kind, correct, concept_key, at or time.time()))


def apply(state: SectionMastery, a: Attempt) -> SectionMastery:
    """`Attempt` 하나를 절 상태에 누적한다. **네 출처가 전부 여기를 지난다.**"""
    wrong = dict(state.wrong_by_concept)
    if not a.correct and a.concept_key:
        wrong[a.concept_key] = wrong.get(a.concept_key, 0) + 1

    by_kind = dict(state.by_kind)
    by_kind[a.kind] = by_kind.get(a.kind, 0) + 1

    return SectionMastery(
        section_id=state.section_id,
        attempts=state.attempts + 1,
        weight=state.weight + a.weight,
        score=state.score + (a.weight if a.correct else 0.0),
        by_kind=by_kind,
        recent=(state.recent + [a.correct])[-RECENT_WINDOW:],
        wrong_by_concept=wrong,
        # 맞혔을 때만 기준점을 옮긴다. 틀렸는데 시계를 리셋하면 **못 꺼냈는데
        # 방금 꺼낸 것으로 쳐서** 복습이 안 돌아온다.
        last_success=a.at if a.correct else state.last_success,
        streak=state.streak + 1 if a.correct else 0,
    )


@dataclass(frozen=True)
class ChapterMastery:
    """목차 하나의 집계 — Rule Engine(분량 배분)의 입력."""

    chapter: str
    sections_total: int
    sections_touched: int
    ratio: float  # 시도한 절들의 가중 정답률
    weak_concepts: tuple[str, ...]
    attempts: int = 0  # 이 목차에서 푼 문항 수(표시용)
    weight: float = 0.0  # 가중 시도량 — **판정할 자격이 있는지**를 본다
    recall: float = 0.0  # 회상 강도 — 시도한 절들의 평균
    sections_due: int = 0  # 복습이 필요한 절 수
    by_kind: dict[str, int] = field(default_factory=dict)

    @property
    def progress(self) -> float:
        """진도율 — 이해도와 다르다. 얼마나 훑었는가."""
        return self.sections_touched / self.sections_total if self.sections_total else 0.0

    @property
    def judged(self) -> bool:
        """이해도를 말할 만큼 풀었는가.

        절에 가드를 걸어놓고 목차엔 안 걸었더니, **한 문제 틀리면 단원 전체가
        "이해도 0%로 낮아 설명을 늘렸습니다"로 뒤집혔다**(실측). 한 문제로
        이해도를 말하는 건 거짓말이다 — 성향에 confidence를 둔 것과 같은 원리로,
        **측정이 부족하면 판정하지 않는다.**
        """
        return self.weight >= MIN_WEIGHT

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


def chapter_summary(
    chapter: str, states: list[SectionMastery], now: float | None = None
) -> ChapterMastery:
    """절 상태들을 목차 단위로 묶는다.

    이해도는 **시도한 절만**으로 낸다. 안 푼 절을 0점으로 세면 진도가 곧
    이해도가 되어, "많이 봤지만 잘 모른다"와 "조금 봤지만 잘 안다"를 구분할 수
    없다. 진도는 progress로 따로 본다.

    가중은 **시도량**으로 한다 — 3문제 푼 절과 10문제 푼 절을 같은 무게로 평균내면
    적게 푼 절의 흔들림이 과대 반영된다. 여기서 시도량은 출처 가중이 들어간
    값이라, 복습으로 확인한 절이 자연히 더 무겁게 잡힌다.
    """
    touched = [s for s in states if s.attempts > 0]
    total_weight = sum(s.weight for s in touched)
    ratio = sum(s.score for s in touched) / total_weight if total_weight else 0.0

    # 절을 넘나들며 반복해서 틀린 개념을 모은다.
    counter: dict[str, int] = {}
    by_kind: dict[str, int] = {}
    for s in touched:
        for key, n in s.wrong_by_concept.items():
            counter[key] = counter.get(key, 0) + n
        for k, n in s.by_kind.items():
            by_kind[k] = by_kind.get(k, 0) + n
    weak = sorted(
        (k for k, n in counter.items() if n >= WEAK_THRESHOLD),
        key=lambda k: (-counter[k], k),
    )

    recall = sum(s.recall(now) for s in touched) / len(touched) if touched else 0.0

    return ChapterMastery(
        chapter=chapter,
        sections_total=len(states),
        sections_touched=len(touched),
        ratio=round(ratio, 3),
        weak_concepts=tuple(weak),
        attempts=sum(s.attempts for s in touched),
        weight=round(total_weight, 3),
        recall=round(recall, 3),
        sections_due=sum(1 for s in touched if s.needs_review(now)),
        by_kind=by_kind,
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
        """준비도 — **네 출처가 모여 나오는 하나의 값.**

        세 가지를 곱한다:

            이해도    맞혔는가          (진단·인출·복습·형성 가중 합산)
            진도      봤는가            (안 본 목차는 0)
            회상 강도  지금도 꺼내지는가  (망각곡선)

        곱하는 이유: 하나라도 0이면 준비된 게 아니다. 다 봤지만 못 맞히면
        준비가 아니고, 잘 맞혔지만 절반만 봤어도 준비가 아니고, 한 달 전에
        잘했지만 지금 못 꺼내면 그것도 준비가 아니다.

        절 수로 가중한다 — 절 26개짜리 목차와 16개짜리를 같은 무게로 평균내면
        작은 목차 하나가 전체를 흔든다. 분량이 곧 비중이다.
        """
        total = sum(c.sections_total for c in self.chapters)
        if not total:
            return 0.0
        weighted = sum(
            c.ratio * c.progress * c.recall * c.sections_total for c in self.chapters
        )
        return round(weighted / total, 3)

    @property
    def understanding(self) -> float:
        """이해도만 — 망각을 빼고 본 값. 준비도가 왜 낮은지 가르는 데 쓴다.

        준비도는 낮은데 이게 높으면 **잊은 것**이고, 둘 다 낮으면 **아직 모르는
        것**이다. 처방이 다르다(복습 vs 다시 학습).
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
    def sections_due(self) -> int:
        """복습이 필요한 절 수 — 화면의 `🔁 복습 N개`."""
        return sum(c.sections_due for c in self.chapters)

    @property
    def by_kind(self) -> dict[str, int]:
        """출처별 푼 문항 수. **누적이 어디서 왔는지** 화면에 보여주는 값이다."""
        out: dict[str, int] = {}
        for c in self.chapters:
            for k, n in c.by_kind.items():
                out[k] = out.get(k, 0) + n
        return out

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
