"""형성평가 에이전트 — 목차 하나를 마쳤는가.

## 인출과 무엇이 다른가

이게 설계의 전부다. 다르지 않으면 **인출 몰아보기**일 뿐이고, 그러면 따로
만들 이유가 없다.

```
인출    화면 **안**   방금 읽은 글에서 꺼낸다        "결합도란?"
형성    화면 **사이**  여러 화면을 가로질러 구별한다   "자료 결합도 vs 제어 결합도"
```

인출은 한 개념을 아는지 본다. 형성은 **배운 것들을 갈라 쓸 수 있는지** 본다.
목차를 다 읽고 나면 개념 하나하나는 알아도 서로 헷갈리는 게 정상이고, 그걸
잡아주는 자리가 여기다.

그래서 문항은 **객관식이 주력**이다. 빈칸은 개념 하나를 꺼내는 것이라 구별을
못 재고, 그건 이미 인출이 하고 있다.

## 프롬프트로 부탁하지 않고 잰다

"여러 화면을 가로지르는 문항을 만들어라"라고만 쓰면 안 지켜진다. 인출에서
겪었다 — "빈칸은 개념마다 하나씩"이 부탁으로만 남아 개념의 19%가 한 번도
안 꺼내졌다. 그래서 여기는 **재는 것**을 먼저 정한다.

```
가로지름  한 문항의 보기에 **서로 다른 화면**의 개념이 둘 이상 섞였는가
          → 순수 로직으로 셀 수 있다. 모델의 자기 신고가 아니다
약점 반영  이 사람이 자주 틀린 개념이 문항에 들어갔는가
```
`MIN_CROSS_RATIO` 미달이면 어느 문항이 왜 걸렸는지 붙여 한 번 다시 만든다.

## 무엇을 물을지는 규칙이 고른다

목차 하나에 개념이 50개가 넘는데 문항은 5개다. 다 물을 수 없으니 **고르는
기준**이 있어야 하고, 그걸 LLM에 맡기면 매번 달라져서 "왜 이걸 물었는지"를
설명할 수 없다.

```
1순위  자주 틀린 개념        약점을 확인하지 않는 평가는 평가가 아니다
2순위  아직 안 풀어본 화면    미측정 자리. 숙련도에 구멍으로 남아 있다
3순위  나머지                원문 순서대로
```
`select_concepts`가 순수 로직으로 고른다.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from app.core.llm.solar import solar_client

from ..blocks import Block, ConceptBrief, _gist, parse_response
from ..retrieval_level import L3_DISCRIMINATE, assess_mcq, mix

# 목차 하나당 문항 수. 많으면 안 푼다 — 안 푼 평가는 데이터가 0이다.
QUESTIONS = 5
# 문항의 이 비율 이상이 화면을 가로질러야 한다. 절반을 못 넘으면 인출과 같다.
MIN_CROSS_RATIO = 0.5
# 재시도는 한 번. 두 번째도 안 되면 목차에 구별할 재료가 없는 것이다.
MAX_RETRY = 1
# 프롬프트에 넣을 개념 상한. 넘으면 모델이 앞쪽만 보고 만든다.
MAX_CONCEPTS = 16


@dataclass(frozen=True)
class FormativeResult:
    blocks: tuple[Block, ...]
    levels: dict[str, int] = field(default_factory=dict)
    # 화면을 가로지른 문항 수 / 전체. 화면에 "종합 문항 3/5"로 쓸 수 있다
    crossing: int = 0
    # 이 평가가 실제로 확인한 약점 개념. **요청이 아니라 들어간 것**이다
    covered_weak: tuple[str, ...] = ()
    retried: bool = False

    @property
    def ok(self) -> bool:
        return bool(self.blocks)

    @property
    def cross_ratio(self) -> float:
        return self.crossing / len(self.blocks) if self.blocks else 0.0


def select_concepts(
    screens: list[tuple[str, tuple[ConceptBrief, ...], int]],
    weak: tuple[str, ...],
    limit: int = MAX_CONCEPTS,
) -> list[ConceptBrief]:
    """무엇을 물을지 고른다. **규칙이 고르므로 이유를 쓸 수 있다.**

    screens: (화면 제목, 개념들, 그 화면의 시도 횟수)
    weak:    이 목차에서 자주 틀린 개념

    약점 → 미측정 화면 → 나머지 순. 같은 화면에서 여러 개를 뽑되, 화면 하나가
    자리를 다 먹지 않게 **화면을 돌아가며** 뽑는다 — 한 화면 개념만 모이면
    가로지르는 문항 자체가 안 나온다.
    """
    weak_set = set(weak)
    priority: list[list[ConceptBrief]] = [[], [], []]  # 약점 / 미측정 / 나머지
    for _title, concepts, attempts in screens:
        for c in concepts:
            if c.key in weak_set:
                priority[0].append(c)
            elif attempts == 0:
                priority[1].append(c)
            else:
                priority[2].append(c)

    out: list[ConceptBrief] = []
    seen: set[str] = set()
    for bucket in priority:
        for c in bucket:
            if c.key in seen:
                continue
            seen.add(c.key)
            out.append(c)
            if len(out) >= limit:
                return out
    return out


def crossing(block: Block, screen_of: dict[str, int]) -> bool:
    """이 문항이 화면을 가로지르는가 — **보기에 다른 화면 개념이 섞였는가.**

    모델이 "종합 문항입니다"라고 신고하는 걸 믿지 않는다. 보기에 실제로 들어간
    개념들이 어느 화면에서 왔는지 세면 되고, 그건 순수 로직이다.
    """
    if block.type != "mcq":
        return False
    options = block.content.get("options") or []
    screens = {screen_of[o] for o in options if o in screen_of}
    return len(screens) >= 2


def _schema(concepts: list[ConceptBrief]) -> str:
    """예시를 **이 단원 개념으로 완성해서** 준다.

    추상 자리를 주면 모델이 그대로 낸다 — 다섯 번 겪었고 인출 쪽 주석에 다 적혀
    있다. 여기선 한 가지가 더 있다: `"다음 설명에 해당하는 것은?"` 같은 상투구는
    `_TEMPLATE_MARKERS`에 걸려 **파서가 통째로 버린다.** 예시가 곧 출력이므로
    예시 자체가 필터를 통과하는 완성 문항이어야 한다(실측: 안 그래서 0문항).

    그리고 보기를 **서로 다른 화면 개념으로** 채운다 — 베껴도 우리가 원하는
    가로지르는 문항이 된다.
    """
    names = [c.key for c in concepts[:4]] or ["개념"]
    while len(names) < 3:
        names.append(f"{names[0]} 아닌 것 {len(names)}")
    # 설명을 문장으로 끊고 나서 묻는다. 정의문 끝에 조사를 붙이면 받침에 따라
    # 어색해진다(실측: "…원칙들 것에 해당하는" — 예시를 그대로 베낀 결과다).
    gist = _gist(concepts[0].definition) if concepts else "그런 성질을 가진 것"
    return f"""{{
  "mcq": [
    {{"question": "{gist}. 이에 해당하는 개념은?",
     "options": {json.dumps(names, ensure_ascii=False)},
     "answer": "{names[0]}",
     "explanation": "왜 그것이고 나머지는 왜 아닌지"}}
  ]
}}"""


def build_prompt(
    chapter_title: str,
    screens: list[tuple[str, tuple[ConceptBrief, ...]]],
    concepts: list[ConceptBrief],
    weak: tuple[str, ...] = (),
    feedback: str = "",
) -> str:
    """형성평가 문항을 만드는 프롬프트.

    **화면별로 묶어서** 준다. 개념을 평평하게 나열하면 어느 게 같이 배운
    것인지 모르고, 그러면 가로지르는 문항을 만들 수가 없다.
    """
    grouped = "\n".join(
        f"[화면 {i + 1}] {title}\n"
        + "\n".join(f"  - {c.key} — {c.definition}" for c in cs if c in concepts)
        for i, (title, cs) in enumerate(screens)
        if any(c in concepts for c in cs)
    )
    weak_part = ""
    if weak:
        weak_part = (
            f"\n[이 학습자가 자주 틀린 것] {' · '.join(weak)}\n"
            "   이 개념들은 **반드시** 문항에 넣어라. 확인 안 하면 평가가 아니다.\n"
        )
    fb = f"\n[이전 시도의 문제]\n{feedback}\n" if feedback else ""

    return f"""너는 **형성평가**를 만드는 에이전트다. 단원 하나를 마친 학습자가 푼다.

[단원] {chapter_title}

아래는 이 단원에서 **화면별로 나눠 배운** 개념들이다.

{grouped}
{weak_part}{fb}
[규칙]
1. **객관식 {QUESTIONS}개**를 만든다. 보기는 3~4개.

2. ★ **화면을 가로지르는 문항이어야 한다.**
   한 문항의 보기에 **서로 다른 화면의 개념**을 섞어라.
   같은 화면 개념만 모으면 이미 푼 인출 문항과 다를 게 없다.
   이 평가의 목적은 "각각을 아는가"가 아니라 **"섞여 있을 때 가를 수 있는가"**다.

3. **헷갈릴 만한 것끼리 붙여라.** 정답과 무관한 보기를 채우면 소거법으로 풀린다.
   비슷한 층위·비슷한 이름·같은 분류의 개념을 오답 보기로 써라.

4. **정답은 위 개념 중 하나를 정확히** 쓴다. 위에 없는 말을 정답으로 쓰지 마라.

5. `explanation`에 **왜 그것이고 나머지는 왜 아닌지**를 쓴다.
   형성평가는 점수를 매기는 자리가 아니라 **가르는 법을 배우는 자리**다.

아래 JSON 객체 하나만 출력한다(설명·코드펜스 금지):
{_schema(concepts)}"""


def _feedback(blocks: list[Block], screen_of: dict[str, int]) -> str:
    """어느 문항이 왜 걸렸는지 짚는다. 뭉뚱그리면 모델이 못 고친다."""
    lines = [
        f'  · "{b.content.get("question", "")[:44]}" — 보기가 전부 같은 화면 개념이다'
        for b in blocks
        if b.type == "mcq" and not crossing(b, screen_of)
    ]
    if not lines:
        return ""
    return (
        "아래 문항이 **한 화면 안에서만** 묻고 있다. 인출 문항과 다를 게 없다.\n"
        "보기에 **다른 화면의 개념**을 섞어 다시 만들어라.\n" + "\n".join(lines[:4])
    )


async def generate(
    chapter_title: str,
    screens: list[tuple[str, tuple[ConceptBrief, ...], int]],
    weak: tuple[str, ...] = (),
) -> FormativeResult:
    """목차 하나의 형성평가를 만들고 **스스로 재서** 필요하면 다시 만든다."""
    concepts = select_concepts(screens, weak)
    if len(concepts) < 2:
        return FormativeResult(blocks=())  # 구별할 게 없으면 형성평가가 성립 안 한다

    screen_of = {c.key: i for i, (_t, cs, _a) in enumerate(screens) for c in cs}
    pairs = [(t, cs) for t, cs, _a in screens]
    keys = [c.key for c in concepts]

    best: FormativeResult | None = None
    feedback = ""
    for attempt in range(MAX_RETRY + 1):
        prompt = build_prompt(chapter_title, pairs, concepts, weak, feedback)
        try:
            raw = await solar_client.generate(
                prompt, response_format={"type": "json_object"}, temperature=0.4
            )
        except Exception as e:  # noqa: BLE001
            print(f"[formative] 생성 실패 {chapter_title}: {type(e).__name__}: {e}")
            break

        blocks = [b for b in parse_response(raw, concepts) if b.type == "mcq"]
        cross = sum(1 for b in blocks if crossing(b, screen_of))
        result = FormativeResult(
            blocks=tuple(blocks),
            levels=mix([assess_mcq(b.content.get("options") or [], keys) for b in blocks]),
            crossing=cross,
            # 요청한 약점이 아니라 **문항에 실제로 들어간** 것만 센다.
            covered_weak=tuple(
                k
                for k in weak
                if any(k in (b.content.get("options") or []) for b in blocks)
            ),
            retried=attempt > 0,
        )
        # 가로지름이 많은 쪽. 같으면 문항이 많은 쪽 — 고치려다 잃으면 손해다.
        if best is None or (result.crossing, len(result.blocks)) > (
            best.crossing,
            len(best.blocks),
        ):
            best = result
        if not blocks or result.cross_ratio >= MIN_CROSS_RATIO:
            break
        feedback = _feedback(blocks, screen_of)
        if not feedback:
            break

    return best or FormativeResult(blocks=())


__all__ = [
    "L3_DISCRIMINATE",
    "MIN_CROSS_RATIO",
    "QUESTIONS",
    "FormativeResult",
    "build_prompt",
    "crossing",
    "generate",
    "select_concepts",
]
