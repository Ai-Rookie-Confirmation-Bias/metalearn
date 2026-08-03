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

묶는 규칙(신뢰도 순):
    ⓪ 원문에서 같은 표 / 같은 항목 아래 있는 개념 = 한 절
       저자가 표 하나에 나란히 넣은 것은 **저자가 내린 묶기 결정**이다.
       ①~③은 우리 추론이므로, 사실이 추론보다 앞선다.
    ① 같은 부모(선수)를 가진 개념 + 그 부모 = 한 절
       부모가 이 목록에 없어도 된다. '애자일 개발'이 개념으로 안 잡혔어도,
       그것을 선수로 공유하는 둘은 같이 배워야 한다.
    ①b 선수로 이어진 사슬 = 한 절
       ①은 형제가 둘 이상이어야 하는데 실측에서 **부모의 76%가 자식 하나뿐**이었다.
       `정보 은닉 → 모듈 → 모듈화`는 형제가 없을 뿐 한 단원이다.
    ② 서로가 서로의 선수(순환) = 한 절
       자료 흐름도 ↔ 자료 사전. 순서를 정할 수 없으니 함께 본다.
    ③ 남은 외톨이는 원문 순서로 묶는다
       교재 저자가 정한 배열이라 그 자체로 의미가 있다.

⚠️ ⓪은 **있으면 쓰고 없으면 안 쓰는** 신호다. `source`를 안 주거나 표·헤딩이
   없는 문서(대학 강의 자료 등)면 ⓪은 아무것도 못 잡고 ①~③이 그대로 돈다.
   특정 교재의 조판에 의존하지 않게 하려는 것이다 — 정처기 요약집에서 잘 되는 것과
   일반 문서에서 안 깨지는 것은 별개로 지켜야 한다.

완벽할 필요 없는 휴리스틱이다. 결과를 보고 규칙을 고친다.
"""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field

from .excerpt import normalize_spaces

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


# 헤딩 앞머리의 조판 기호. 한 번에 걷어내야 `# ※ 제목`이 `제목`이 된다.
_HEAD_MARK = re.compile(r"^[\s#■※▶★◆●○*·\-\[\]()]+")
# 이런 제목은 절 이름으로 아무것도 알려주지 않는다 — 개념명으로 대체한다.
_EMPTY_TITLES = {
    "종류", "특징", "개요", "정의", "구성", "구성요소", "방법", "분류",
    "예시", "예", "참고", "비고", "설명", "내용", "기타", "요약", "표",
}


def _squash(text: str) -> str:
    """공백을 없앤 비교용 문자열. PDF 추출본은 띄어쓰기가 들쭉날쭉하다."""
    return re.sub(r"\s+", "", normalize_spaces(text))


def _blocks(source: str) -> list[str]:
    """원문을 표 / 항목 단위 덩어리로 나눈다.

    헤딩은 항상 새 덩어리를 열고, 표 행은 표끼리만 이어 붙인다.
    표도 헤딩도 없는 문서면 전체가 덩어리 하나가 되어 ⓪이 자연히 무력해진다.
    """
    out: list[str] = []
    cur: list[str] = []
    mode = ""
    for line in source.splitlines():
        s = line.strip()
        kind = "table" if s.startswith("|") else "head" if s.startswith("#") else "body"
        if kind == "head" or (kind == "table") != (mode == "table"):
            if cur:
                out.append("\n".join(cur))
            cur, mode = [line], kind
        else:
            cur.append(line)
            mode = mode or kind
    if cur:
        out.append("\n".join(cur))
    return [b for b in out if b.strip()]


def _block_title(blocks: list[str], i: int, fallback: str) -> str:
    """덩어리 제목 — 자기 헤딩, 없으면 바로 앞 헤딩(표는 제목이 앞에 있다)."""
    for j in (i, i - 1):
        if j < 0:
            continue
        first = blocks[j].strip().splitlines()[0]
        if not first.strip().startswith("#"):
            continue
        t = _HEAD_MARK.sub("", first).strip()
        t = t.split(" : ")[0].split(" (")[0].strip(" :·-]）)")
        if 2 <= len(t) <= 40 and t not in _EMPTY_TITLES:
            return t
    return fallback


def _structure_groups(
    concepts: list[Concept], source: str
) -> list[tuple[str, str, set[str]]]:
    """ⓠ 원문 구조로 묶는다. (제목, 이유, 개념 key들) 목록.

    개념명을 원문에서 못 찾으면(표기가 달라서) 그냥 넘긴다 — ①~③이 받는다.
    """
    if not source.strip():
        return []
    blocks = _blocks(source)
    squashed = [_squash(b) for b in blocks]
    owner: dict[int, list[str]] = defaultdict(list)
    for c in concepts:
        key = _squash(c.key)
        if not key:
            continue
        for i, body in enumerate(squashed):
            if key in body:
                owner[i].append(c.key)
                break

    out: list[tuple[str, str, set[str]]] = []
    for i in sorted(owner):
        keys = owner[i]
        # 혼자면 묶음이 아니고, 정원을 넘으면 절이 아니라 다시 조각이다.
        # 둘 다 ①~③으로 넘겨 선수 관계로 다시 나누게 한다.
        if not 2 <= len(keys) <= MAX_PER_SECTION:
            continue
        title = _block_title(blocks, i, keys[0])
        kind = "표" if blocks[i].strip().startswith("|") else "항목"
        out.append((title, f"교재가 이 {len(keys)}개를 같은 {kind}에 묶어 설명합니다", set(keys)))
    return out


def _positions(concepts: list[Concept], source: str) -> dict[str, int]:
    """개념이 원문에 처음 나오는 위치. 절 순서를 정하는 데 쓴다.

    `Concept.order`는 파싱 md의 나열 순서인데 실측해보니 **가나다순**이었다.
    그걸로 정렬하면 학습 순서가 교재와 완전히 어긋난다.
    """
    body = _squash(source)
    out: dict[str, int] = {}
    for c in concepts:
        at = body.find(_squash(c.key))
        if at >= 0:
            out[c.key] = at
    return out


def _chains(by_key: dict[str, Concept], taken: set[str]) -> list[set[str]]:
    """선수 관계로 이어진 사슬을 통째로 묶는다. 큰 사슬부터.

    ①은 형제가 `MIN_SIBLINGS`명 이상이어야 묶는데, 실측에서 **부모의 76%가
    자식 하나뿐**이었다(필기 176/232). 그래서 관계가 멀쩡히 있는 개념의
    30~53%가 형제가 없다는 이유만으로 잡동사니 절로 빠졌다.

    `정보 은닉 → 모듈 → 모듈화`는 형제가 없을 뿐 교과서가 한 단원으로 묶는
    사슬이다. 형제 수 대신 **연결되어 있는가**로 본다.

    부모가 개념 목록에 없으면 이을 데가 없으므로 ③으로 넘어간다.
    """
    live = {k for k in by_key if k not in taken}
    adj: dict[str, set[str]] = defaultdict(set)
    for key in live:
        for p in by_key[key].prerequisites:
            if p in live:
                adj[key].add(p)
                adj[p].add(key)

    seen: set[str] = set()
    out: list[set[str]] = []
    for start in sorted(live):  # 정렬해야 같은 입력에 같은 결과가 나온다
        if start in seen or start not in adj:
            continue
        comp: set[str] = set()
        stack = [start]
        while stack:
            cur = stack.pop()
            if cur in comp:
                continue
            comp.add(cur)
            stack.extend(adj[cur] - comp)
        seen |= comp
        if len(comp) >= 2:
            out.append(comp)
    out.sort(key=lambda s: (-len(s), min(s)))
    return out


def _root_of(keys: set[str], by_key: dict[str, Concept]) -> str:
    """사슬의 머리 — 사슬 안에 자기 선수가 없는 개념. 그게 절 제목이 된다."""
    heads = [k for k in keys if not (set(by_key[k].prerequisites) & keys)]
    return min(heads or list(keys), key=lambda k: (by_key[k].order, k))


def _fit(group: set[str], anchor: str | None, by_key: dict[str, Concept]) -> set[str]:
    """정원(`MAX_PER_SECTION`)에 맞춘다. **기준 개념은 절대 밀어내지 않는다.**

    실측 사고: `행위 패턴`의 하위가 10종이라 정원이 꽉 차서 정작 부모인
    `행위 패턴`이 밀려났고, 같은 이름의 절이 둘로 갈렸다.
    """
    if len(group) <= MAX_PER_SECTION:
        return group
    keep = {anchor} if anchor and anchor in group else set()
    rest = sorted(group - keep, key=lambda k: (by_key[k].order, k))
    return keep | set(rest[: MAX_PER_SECTION - len(keep)])


def _chunk_leftovers(items: list[Concept], size: int) -> list[list[Concept]]:
    """외톨이를 원문 순서대로 size개씩 자른다. 마지막 조각이 1개면 앞에 붙인다."""
    out = [items[i : i + size] for i in range(0, len(items), size)]
    if len(out) > 1 and len(out[-1]) == 1:
        out[-2].extend(out.pop())
    return out


def group_into_sections(concepts: list[Concept], source: str = "") -> list[Section]:
    """개념 목록을 절로 묶는다.

    `source`(그 조각의 원문)를 주면 ⓪(원문 구조)과 원문 기준 절 순서가 켜진다.
    안 주면 ①~③만으로 도는 예전 동작 그대로다 — 원문을 못 쓰는 호출부가 있어도
    깨지지 않아야 하고, 구조 없는 문서에서도 같은 경로로 떨어져야 한다.

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

    # ⓪ 원문 구조 — 저자가 이미 내린 결정이라 우리 추론보다 앞선다.
    for title, reason, keys in _structure_groups(concepts, source):
        keys = {k for k in keys if k not in taken}
        if len(keys) >= 2:
            emit(keys, title, reason)

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
        group = _fit(group, parent, by_key)
        emit(group, parent, f"'{parent}'을(를) 함께 알아야 이해되는 개념들입니다")

    # ①-b 사슬 — 형제가 없어도 선수로 이어져 있으면 한 절이다.
    for comp in _chains(by_key, taken):
        comp = {k for k in comp if k not in taken}
        if len(comp) < 2:
            continue
        root = _root_of(comp, by_key)
        emit(_fit(comp, root, by_key), root, f"'{root}'에서 이어지는 개념들입니다")

    # ③ 남은 것은 원문 순서대로
    leftovers = [c for c in ordered if c.key not in taken]
    for batch in _chunk_leftovers(leftovers, LEFTOVER_TARGET):
        emit(
            {c.key for c in batch},
            batch[0].key,
            "교재에서 이어서 나오는 내용입니다",
        )

    # 절 자체의 순서도 원문을 따른다 — 학습 순서가 교재와 어긋나면 혼란스럽다.
    # 절 순서는 교재를 따른다. 원문이 있으면 등장 위치로, 없으면 입력 순서로.
    # 원문에서 이름을 못 찾은 절(8~11%)은 기준이 없으므로 뒤로 보낸다.
    if source:
        pos = _positions(concepts, source)
        far = len(_squash(source)) + 1
        sections.sort(key=lambda s: min((pos[c.key] for c in s.concepts if c.key in pos), default=far))
    else:
        sections.sort(key=lambda s: min(c.order for c in s.concepts))

    # 제목이 겹치면 화면에서 같은 절로 보인다 — 뒤에 나온 것에 번호를 붙인다.
    used: dict[str, int] = {}
    out: list[Section] = []
    for i, s in enumerate(sections):
        n = used[s.title] = used.get(s.title, 0) + 1
        title = s.title if n == 1 else f"{s.title} ({n})"
        out.append(Section(title=title, concepts=s.concepts, reason=s.reason, order=i))
    return out


def _title_of(keys: set[str], by_key: dict[str, Concept], ordered: list[Concept]) -> str:
    """절 제목 — 원문에 먼저 나온 개념 이름을 쓴다(임시).

    나중에 LLM으로 묶음을 아우르는 이름을 짓게 할 수 있지만, 그 전에도
    화면에 뭔가는 떠야 하므로 결정적인 폴백을 둔다.
    """
    for c in ordered:
        if c.key in keys:
            return c.key
    return next(iter(sorted(keys)))
