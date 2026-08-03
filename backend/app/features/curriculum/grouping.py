"""[순수로직] 개념을 학습 단위(절)로 묶는다.

DB·LLM 비의존. 커리큘럼 엔진의 **첫 단계**이며, 이후 모든 것이 이 위에 선다.

왜 필요한가:
    파싱은 `목차 → 조각 → 개념`으로 준다. 그런데 실측(pilgi.pdf)에서
    개념 533개 · 조각 18개(평균 3,438자)였다. 둘 다 학습 단위가 못 된다.
      · 개념 단위(533) — 개념당 블록 6개면 3,198개. 하루 30분 × 8일이면 개당 38초
      · 조각 단위(18)  — 한 조각이 3,982자. 한 화면에 담기지 않는다
    그래서 중간 단위가 필요하다. 개념 5~10개, 원문 800~1,200자.

왜 이 크기인가(문항 생성 실측):
    원문을 통째로 주고 생성시키면 LLM이 눈에 띄는 것만 판다 — 커버리지 39%,
    문항 수를 3배로 늘려도 오르지 않았다. 구간으로 쪼개 구간마다 만들게 하니
    76%가 됐다. 학습 블록도 같다. **한 번에 요구하는 양이 작아야 한다.**

묶는 규칙:
    ① 같은 부모(선수)를 가진 개념 + 그 부모 = 한 절
       부모가 이 목록에 없어도 된다. '애자일 개발'이 개념으로 안 잡혔어도,
       그것을 선수로 공유하는 둘은 같이 배워야 한다.
    ② 서로가 서로의 선수(순환) = 한 절
       자료 흐름도 ↔ 자료 사전. 순서를 정할 수 없으니 함께 본다.
    ③ 남은 외톨이는 원문 순서로 묶는다
       교재 저자가 정한 배열이라 그 자체로 의미가 있다.

완벽할 필요 없는 휴리스틱이다. 결과를 보고 규칙을 고친다.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

# 한 절에 너무 많으면 학습 단위가 아니라 다시 조각이 된다.
MAX_PER_SECTION = 10
# 외톨이를 묶을 때의 목표 크기. 2개짜리 절이 여럿 생기면 진도가 잘게 끊긴다.
LEFTOVER_TARGET = 4
# 이보다 적은 개념이 공유하는 부모는 묶음 기준이 못 된다(그냥 선수 관계일 뿐).
MIN_SIBLINGS = 2


@dataclass(frozen=True)
class Concept:
    """파싱이 넘기는 개념 하나."""

    key: str  # 개념명 — 지금은 이름이 곧 식별자(파싱 출력이 이름 참조라서)
    definition: str = ""
    # 선수 개념의 key 목록. 이 목록 밖의 개념을 가리켜도 된다.
    prerequisites: tuple[str, ...] = ()
    order: int = 0  # 원문 등장 순서
    chunk_id: str | None = None


@dataclass(frozen=True)
class Section:
    """학습 단위 하나 = 한 화면 분량의 개념 묶음."""

    title: str
    concepts: tuple[Concept, ...]
    # 왜 이렇게 묶였는지. 화면의 ⚡ 표시와 디버깅에 그대로 쓴다
    # (판단을 규칙이 하므로 이유를 쓸 수 있다 — 서비스 정의의 전제).
    reason: str
    order: int = 0

    @property
    def size(self) -> int:
        return len(self.concepts)


def _cycles(by_key: dict[str, Concept]) -> list[set[str]]:
    """서로가 서로의 선수인 묶음을 찾는다.

    위상 정렬이 안 되므로 순서를 정할 수 없다 — 함께 배우는 수밖에 없다.
    2-사이클(A↔B)만 본다. 3개 이상 얽힌 경우는 실측에서 없었고, 있어도
    ①규칙이 대개 같이 묶어준다.
    """
    found: list[set[str]] = []
    seen: set[frozenset[str]] = set()
    for key, c in by_key.items():
        for p in c.prerequisites:
            other = by_key.get(p)
            if other is None or key not in other.prerequisites:
                continue
            pair = frozenset({key, p})
            if pair not in seen:
                seen.add(pair)
                found.append(set(pair))
    return found


def _parent_groups(
    by_key: dict[str, Concept], taken: set[str]
) -> list[tuple[str, set[str]]]:
    """같은 부모를 공유하는 개념들을 모은다. 큰 묶음부터 돌려준다.

    부모가 개념 목록에 없어도 그룹의 기준이 된다 — 파싱이 '애자일 개발'을
    개념으로 안 잡았어도, 그것을 선수로 공유하는 개념들은 한 단원이다.
    """
    children: dict[str, set[str]] = defaultdict(set)
    for key, c in by_key.items():
        if key in taken:
            continue
        for p in c.prerequisites:
            children[p].add(key)

    groups = [(p, ks) for p, ks in children.items() if len(ks) >= MIN_SIBLINGS]
    # 큰 묶음을 먼저 확정한다. 작은 것부터 잡으면 큰 묶음이 조각난다.
    groups.sort(key=lambda t: (-len(t[1]), t[0]))
    return groups


def _chunk_leftovers(items: list[Concept], size: int) -> list[list[Concept]]:
    """외톨이를 원문 순서대로 size개씩 자른다. 마지막 조각이 1개면 앞에 붙인다."""
    out = [items[i : i + size] for i in range(0, len(items), size)]
    if len(out) > 1 and len(out[-1]) == 1:
        out[-2].extend(out.pop())
    return out


def group_into_sections(concepts: list[Concept]) -> list[Section]:
    """개념 목록을 절로 묶는다.

    입력 순서와 무관하게 결정적이다 — 같은 입력이면 같은 결과가 나와야
    "왜 이렇게 묶였는지"를 화면에 쓸 수 있다.
    """
    if not concepts:
        return []

    by_key = {c.key: c for c in concepts}
    ordered = sorted(concepts, key=lambda c: (c.order, c.key))
    taken: set[str] = set()
    sections: list[Section] = []

    def emit(keys: set[str], title: str, reason: str) -> None:
        members = tuple(c for c in ordered if c.key in keys)
        if not members:
            return
        sections.append(Section(title=title, concepts=members, reason=reason))
        taken.update(keys)

    # ② 순환부터 — 순서를 정할 수 없으므로 무조건 함께 간다.
    for cyc in _cycles(by_key):
        if cyc & taken:
            continue
        names = " ↔ ".join(sorted(cyc))
        emit(cyc, _title_of(cyc, by_key, ordered), f"서로가 서로의 선수입니다 ({names})")

    # ① 같은 부모를 공유하는 개념들 + 그 부모
    for parent, kids in _parent_groups(by_key, taken):
        kids = {k for k in kids if k not in taken}
        if len(kids) < MIN_SIBLINGS:
            continue
        group = set(kids)
        # 부모가 개념 목록에 있으면 같이 배운다(UML과 그 다이어그램들).
        if parent in by_key and parent not in taken:
            group.add(parent)
        if len(group) > MAX_PER_SECTION:
            group = set(sorted(group, key=lambda k: by_key[k].order)[:MAX_PER_SECTION])
        emit(group, parent, f"'{parent}'을(를) 함께 알아야 이해되는 개념들입니다")

    # ③ 남은 것은 원문 순서대로
    leftovers = [c for c in ordered if c.key not in taken]
    for batch in _chunk_leftovers(leftovers, LEFTOVER_TARGET):
        emit(
            {c.key for c in batch},
            batch[0].key,
            "교재에서 이어서 나오는 내용입니다",
        )

    # 절 자체의 순서도 원문을 따른다 — 학습 순서가 교재와 어긋나면 혼란스럽다.
    sections.sort(key=lambda s: min(c.order for c in s.concepts))
    return [
        Section(title=s.title, concepts=s.concepts, reason=s.reason, order=i)
        for i, s in enumerate(sections)
    ]


def _title_of(keys: set[str], by_key: dict[str, Concept], ordered: list[Concept]) -> str:
    """절 제목 — 원문에 먼저 나온 개념 이름을 쓴다(임시).

    나중에 LLM으로 묶음을 아우르는 이름을 짓게 할 수 있지만, 그 전에도
    화면에 뭔가는 떠야 하므로 결정적인 폴백을 둔다.
    """
    for c in ordered:
        if c.key in keys:
            return c.key
    return next(iter(sorted(keys)))
