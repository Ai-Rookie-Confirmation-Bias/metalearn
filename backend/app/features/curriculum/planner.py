"""[순수로직] 커리큘럼 배분 — 학습 상태를 보고 목차마다 얼마나 볼지 정한다.

DB·LLM 비의존. **여기가 "AI가 나를 보고 바꿨다"의 실체다.**

## 왜 규칙인가

같은 상태에 같은 결과가 나와야 화면에 이유를 쓸 수 있다. LLM에게 "이 사람
상태를 보고 커리큘럼을 짜줘"라고 하면 매번 달라지고, 왜 그렇게 됐는지 설명할
수 없다. AI는 **설명을 쓰는 데**만 쓰고 배분은 규칙이 한다.

## 목차 순서는 바꾸지 않는다

실측: 선수관계의 96~99%가 **같은 목차 안**에서 일어난다(목차를 넘는 것은
필기 1%·실기 4%). 교재 저자가 이미 선후관계를 고려해 목차를 짰다는 뜻이고,
재배치해서 얻을 게 없다. 게다가 순서가 흔들리면 어디쯤 왔는지 감각이 사라지고,
시험 범위가 교재 목차대로인 학습자에게는 오히려 불안하다.

**바뀌는 것은 순서가 아니라 분량과 밀도다.**
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace

from app.features.curriculum.excerpt import category_words
from app.features.curriculum.grouping import Concept, Section
from app.features.curriculum.mastery import (
    SHAKY,
    SOLID,
    ChapterMastery,
)

# 한 절 설명에 녹일 약점 개념 상한. 많으면 설명이 산만해져 본 내용이 묻힌다.
MAX_TIE_IN = 2

# ── 보충 화면 삽입 ────────────────────────────────────────────────
# 몇 번 틀려야 화면을 하나 끼우나. 한두 번은 설명 안 tie_in으로 짚고 넘어간다 —
# **한 번 틀렸다고 화면을 만들면 실수 한 번이 진도를 막는다.** 절에 MIN_WEIGHT를
# 걸고 목차에 judged를 건 것과 같은 원리다: 측정이 부족하면 판정하지 않는다.
INSERT_AFTER_WRONG = 3
# 목차 하나에 끼울 수 있는 보충 화면 수. 넘으면 보충이 본 내용을 덮는다.
MAX_INSERT_PER_CHAPTER = 2
# 보충 화면 하나에 담을 개념 수. 결손을 짚는 자리라 원래 화면(3)보다 좁게 본다.
SUPPLEMENT_SIZE = 2

# 배분 단계. 이해도가 낮을수록 절을 더 본다.
DEEP = "deep"  # 약함 — 절을 늘리고 약점 개념을 녹인다
NORMAL = "normal"
COMPRESSED = "compressed"  # 잘 앎 — 핵심만, 비유 생략

# 압축 시 실제로 줄이는 비율. 0으로 만들지 않는다 —
# "이미 아니까 건너뛰세요"는 개인화가 아니라 방치다. 확인은 하고 넘어간다.
COMPRESS_RATIO = 0.5
# 보강 시 늘리는 비율. 무한정 늘리면 진도가 안 나간다.
DEEPEN_RATIO = 1.5


def mode_block(mode: str) -> str:
    """설명 프롬프트에 붙일 **분량 지시**.

    `plan.mode`가 화면에만 뜨고 설명은 안 바뀌면 "커리큘럼이 바뀌었다"가 거짓이다.
    배분 규칙이 정한 모드를 **생성 지시로 바꿔** 같은 규칙이 글에도 닿게 한다.
    """
    if mode == DEEP:
        return (
            "[이 단원의 분량 — 설명을 늘림]\n"
            "- 개념마다 **한 문단 이상** 써라. 왜 필요한지·어디서 쓰이는지까지.\n"
            "- 비유나 예를 아끼지 마라."
        )
    if mode == COMPRESSED:
        return (
            "[이 단원의 분량 — 핵심만]\n"
            "- **결론과 핵심만** 짧게. 배경·유래·반례는 생략하라.\n"
            "- 비유는 넣지 마라(JSON null). 이미 아는 사람에게 비유는 소음이다."
        )
    return ""


@dataclass(frozen=True)
class ChapterPlan:
    """목차 하나에 대한 배분 결정."""

    chapter: str
    order: int  # 교재 순서 그대로. 절대 바뀌지 않는다
    mode: str  # deep | normal | compressed
    sections_total: int
    sections_planned: int  # 실제로 볼 절 수
    weak_concepts: tuple[str, ...]  # 다음 설명에 녹일 대상
    reason: str  # 화면의 ⚡ 표시에 그대로 쓴다

    @property
    def changed(self) -> bool:
        return self.mode != NORMAL


def plan_chapter(
    order: int, summary: ChapterMastery, weak_from_previous: tuple[str, ...] = ()
) -> ChapterPlan:
    """목차 하나의 배분을 정한다.

    weak_from_previous: **앞 목차 형성평가에서 약했던 개념.** 새 단원을 만들지
    않고 이 목차 설명에 녹인다 — 따로 떼어 배운 개념보다 지금 배우는 것과
    엮어서 설명한 개념이 더 잘 붙기 때문이다.
    """
    total = summary.sections_total
    weak = tuple(dict.fromkeys(summary.weak_concepts + weak_from_previous))

    # 아직 안 본 목차, 또는 **판정하기엔 너무 적게 푼 목차**는 표준으로 둔다.
    #
    # 실측 사고: 한 문제 틀리자마자 단원이 `deep`으로 바뀌고 화면에
    # "이해도 0%로 낮아 설명을 늘렸습니다"가 떴다. 한 문제로 이해도를 말하는 건
    # 거짓말이다. 절에는 `MIN_WEIGHT` 가드를 걸어놓고 목차엔 안 걸었던 것 —
    # **측정이 부족하면 판정하지 않는다**는 원칙은 층이 달라도 같다.
    if summary.sections_touched == 0 or not summary.judged:
        mode, planned, reason = NORMAL, total, ""
        if weak_from_previous:
            mode = DEEP
            planned = max(total, round(total * DEEPEN_RATIO))
            reason = (
                f"앞 단원에서 '{weak_from_previous[0]}'이(가) 약했습니다. "
                "따로 배우지 않고 이 단원 설명에 함께 녹입니다."
            )
        return ChapterPlan(summary.chapter, order, mode, total, planned, weak, reason)

    if summary.ratio < SHAKY:
        return ChapterPlan(
            summary.chapter,
            order,
            DEEP,
            total,
            max(total, round(total * DEEPEN_RATIO)),
            weak,
            f"이해도 {summary.ratio:.0%}로 낮아 설명을 늘렸습니다."
            + (f" 특히 '{weak[0]}'을(를) 자주 틀리셨습니다." if weak else ""),
        )

    if summary.ratio >= SOLID:
        return ChapterPlan(
            summary.chapter,
            order,
            COMPRESSED,
            total,
            max(1, round(total * COMPRESS_RATIO)),
            weak,
            f"이해도 {summary.ratio:.0%}로 높아 핵심만 보여드립니다. 비유는 생략됩니다.",
        )

    return ChapterPlan(summary.chapter, order, NORMAL, total, total, weak, "")


def plan_course(
    summaries: list[ChapterMastery], carry_over: dict[str, tuple[str, ...]] | None = None
) -> list[ChapterPlan]:
    """과목 전체 배분. **입력 순서(=교재 목차 순서)를 그대로 유지한다.**

    carry_over: 목차명 → 그 목차 설명에 녹일 약점 개념. 앞 목차의 형성평가
    결과를 호출측이 여기에 담아 넘긴다.
    """
    carry = carry_over or {}
    return [
        plan_chapter(i, s, carry.get(s.chapter, ()))
        for i, s in enumerate(summaries)
    ]


def bar(plan: ChapterPlan, width: int = 12) -> str:
    """분량 막대 — 순서가 안 바뀌는 대신 이게 자라고 줄어드는 걸 보여준다."""
    if plan.sections_total == 0:
        return ""
    filled = max(1, round(width * plan.sections_planned / plan.sections_total))
    return "▓" * min(filled, width * 2)


# 형성평가가 열리는 진도. 이 비율 이상의 화면을 봐야 "단원을 마쳤다"로 친다.
FORMATIVE_UNLOCK = 0.6


def formative_ready(summary: ChapterMastery) -> tuple[bool, str]:
    """형성평가를 열어도 되는가. **잠그는 것은 평가뿐이다.**

    서비스 정의: 학습은 절대 잠그지 않는다(integration이 학습을 잠갔다가 이탈을
    겪었다). 대신 평가는 잠근다 — 안 배운 걸 묻는 시험은 측정이 아니라 좌절이다.

    진도로만 본다. **이해도로 잠그면 안 된다** — 못 하는 사람일수록 확인할 기회가
    사라져서, 도와야 할 사람에게서 도구를 뺏는 꼴이 된다.

    돌려주는 문장은 화면에 그대로 나간다. 잠갔으면 **얼마나 더 해야 하는지**까지
    말해야 한다. "잠김"만 띄우면 무엇을 하라는 건지 알 수 없다.
    """
    if summary.sections_total == 0:
        return False, "이 단원에는 학습할 화면이 없습니다."
    if summary.progress >= FORMATIVE_UNLOCK:
        return True, ""
    need = -(-int(summary.sections_total * FORMATIVE_UNLOCK) // 1) - summary.sections_touched
    return False, (
        f"단원 평가는 화면을 {FORMATIVE_UNLOCK:.0%} 이상 학습하면 열립니다. "
        f"{max(1, need)}개 더 보시면 됩니다."
    )


def supplement_sections(
    sections: Sequence[Section],
    wrong_by_concept: Mapping[str, int],
    pool: Mapping[str, Concept],
) -> list[Section]:
    """원문 화면 목록 → **보충 화면이 끼워진 목록.**

    반복해서 틀린 개념이 다음 화면의 **선수**이면, 그 화면 바로 앞에 그 개념만
    담은 화면을 하나 끼운다. 결손을 안고 다음 개념으로 넘어가면 거기서도 틀리고,
    그게 쌓이면 어디서부터 막혔는지 학습자가 못 찾는다.

    ## 단원은 만들지 않는다

    파싱팀 `origin: inserted`(**단원** 삽입)를 거절한 건 그대로다 — 목차 목록이
    바뀌면 "목차는 고정"이 깨진다. **화면은 다르다.** 1단원이 1.29에서 1.30이
    되는 건 목차가 안 바뀐 것이고, 담는 개념도 이미 문서 안에 있는 것이라
    없던 내용을 지어내지 않는다.

    ## 순수 함수다

    같은 상태면 같은 결과가 나와야 한다. 화면을 새로고침할 때마다 보충이
    생겼다 사라지면 학습자는 자기가 뭘 보고 있는지 알 수 없다. 그래서
    `section_id`도 개념명에서 결정적으로 만든다(`supp::개념명`) — 진도 기록이
    붙어 있어야 다시 열어도 이어진다.

    ⚠️ 진도 분모에는 안 들어간다(`Section.origin` → `chapter_summary`).
       끼울수록 진도가 뒤로 가면 학습을 한 사람이 벌을 받는다.

    wrong_by_concept: 문서 전체에서 개념별로 틀린 횟수.
    pool: 개념명 → 개념. **이 목차 밖 개념도 들어 있어야 한다** — 선수는 앞
          목차에 있는 경우가 흔하다.
    """
    out: list[Section] = []
    used: set[str] = set()
    inserted = 0

    for section in sections:
        if inserted < MAX_INSERT_PER_CHAPTER:
            mine = set(section.concept_keys)
            # 이 화면의 선수 중, 반복해서 틀렸고, 아직 안 짚은 것.
            picks = [
                key
                for c in section.concepts
                for key in c.prerequisites
                if key not in mine
                and key not in used
                and key in pool
                and wrong_by_concept.get(key, 0) >= INSERT_AFTER_WRONG
            ]
            # 같은 화면을 위한 보충은 **하나로 묶는다.** 개념마다 화면을 만들면
            # 목차가 보충으로 뒤덮인다.
            picks = list(dict.fromkeys(picks))[:SUPPLEMENT_SIZE]
            if picks:
                used.update(picks)
                inserted += 1
                out.append(_supplement(picks, pool, wrong_by_concept, section, len(out)))

        out.append(replace(section, order=len(out)))

    return out


def _supplement(
    keys: list[str],
    pool: Mapping[str, Concept],
    wrong_by_concept: Mapping[str, int],
    before: Section,
    order: int,
) -> Section:
    """보충 화면 하나. 제목과 이유는 규칙이 쓴다 — LLM이 아니라."""
    concepts = tuple(pool[k] for k in keys)
    head = keys[0]
    times = wrong_by_concept.get(head, 0)
    label = head if len(keys) == 1 else f"{head} 외 {len(keys) - 1}개"
    return Section(
        title=f"{label} 다시 보기",
        concepts=concepts,
        # 화면에 그대로 나간다. **왜 여기 있는지**를 말해주지 않으면
        # 교재에 원래 있던 내용이라고 오해한다.
        reason=(
            f"'{head}'을(를) {times}번 틀리셨습니다. "
            f"다음 화면 '{before.title}'의 선수 개념이라 먼저 짚고 갑니다."
        ),
        order=order,
        source="\n\n".join(c.definition for c in concepts if c.definition),
        section_id=f"supp::{head}",
        origin="inserted",
    )


def weak_for_section(
    section: Section, recent_wrong: list[str], all_keys: list[str]
) -> tuple[str, ...]:
    """이 화면 설명에 녹일 약점 개념 — **이어지는 것만** 고른다.

    yoonhs 지적: 약점을 목차 단위로만 넘기면 목차 하나가 화면 20개라 반영이
    20화면 뒤에 나타난다. 학습자는 체감을 못 한다. 화면 단위로 바로 짚어야 한다.

    다만 아무 화면에나 끌고 오면 설명이 산만해진다. **이어지는 지점이 있을 때만**
    녹인다:

      ① 선수 관계   약점이 이 화면 개념의 선수이거나, 그 반대이거나
      ② 분류어 공유  `자료 결합도`와 `제어 결합도`는 `결합도`를 공유한다

    ⚠️ 이 화면에 이미 들어 있는 개념은 뺀다 — 지금 배우는 걸 "지난번에 틀렸다"고
    짚는 건 이상하다. 그건 이 화면 안에서 다시 물으면 된다.

    최근 것부터 본다(`recent_wrong`은 뒤가 최신).
    """
    if not recent_wrong:
        return ()
    mine = set(section.concept_keys)
    prereq = {p for c in section.concepts for p in c.prerequisites}
    cats = category_words(all_keys, min_share=2)

    def tail(key: str) -> str:
        parts = key.split()
        return parts[-1] if len(parts) >= 2 and parts[-1] in cats else ""

    my_tails = {t for k in mine if (t := tail(k))}

    out: list[str] = []
    for key in reversed(recent_wrong):
        if key in mine:
            continue  # 지금 배우는 개념이면 이 절에서 다시 물으면 된다
        linked = key in prereq or any(
            key in c.prerequisites for c in section.concepts
        )
        shares = bool((t := tail(key)) and t in my_tails)
        if linked or shares:
            out.append(key)
        if len(out) >= MAX_TIE_IN:
            break
    return tuple(out)
