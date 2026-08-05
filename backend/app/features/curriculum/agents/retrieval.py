"""인출 에이전트 — 절 + 설명 → 빈칸·객관식.

## 왜 떼어냈나

한 프롬프트가 설명·비유·빈칸·객관식을 다 만들 때 지시가 서로 밀어냈다.
빈칸 유형을 자세히 쓸수록 설명 규칙이 묻히고, 결국 **문항의 63%가 정의문
되읽기**가 됐다(판정기 실측). 인출만 담당하면 유형 지시를 여기 몰아 쓸 수 있다.

## 재료가 달라지는 게 핵심

전에는 `개념 정의문`이 주 재료였다. 정의가 유일하게 풍부하니 거기서만 문항이
나왔고, 그래서 정의를 복사해 이름만 비운 문항이 쌓였다.

인출 에이전트는 **방금 만든 설명 본문**을 받는다. 그래야
  · "읽게 하지 않고 꺼내게 한다"가 성립한다 — 방금 읽은 글에서 꺼내는 것이다
  · 설명은 개념들을 **연결해서** 쓰므로 관계를 묻는 문항이 나올 수 있다
  · 정의문을 옮기지 말라고 할 근거가 생긴다(옮길 정의가 재료가 아니므로)

## 자기 품질을 자기가 잰다 — 두 가지를 잰다

`retrieval_level`이 판정한다. 시키는 쪽과 재는 쪽이 같으면 자기 채점이 되므로
판정은 순수 로직에 두고 여기서 호출만 한다.

```
품질  L1(정의 되읽기)이 과한가   → 전체를 다시 만들고 나은 쪽을 쓴다
누락  안 물어본 개념이 있는가     → 그 개념만 다시 요청해 덧붙인다
```

**둘의 처방이 다르다.** L1이 높으면 만드는 방식이 잘못된 것이라 다시 만들어야
하고, 누락은 나머지가 멀쩡하므로 **부족분만 채우면 된다.** 누락을 전체 재생성으로
고치려 하면 잘 나온 문항까지 흔들린다.

⚠️ 재시도 결과가 더 나쁘면 처음 것을 쓴다. 개선하려다 문항을 잃으면 손해다.
보충은 덧붙이기라 이 위험이 없다 — 그래서 재생성이 아니라 보충으로 짰다.

## 왜 게이트가 필요한가 (실측)

"빈칸은 개념마다 하나씩"이라고 **프롬프트로 요구만 하고 강제가 없었다.**
14절 실측: 인출된 개념 39/48 = 81%, 빠짐 없는 절 6/14 = 43%. 재시도는
**한 번도 안 걸렸다** — L1만 보고 있었고 `gap`은 계산해서 화면에 내보내기만
했기 때문이다. 인출을 절 단위 → 개념 단위로 바꿀 때 고쳤다고 생각한 문제가
단위만 바뀐 채 그대로 남아 있었다.

안 물어본 개념은 숙련도에 **영영 미측정으로 남는다.** 누적 모델(`mastery`)의
입력이 비는 것이라 개인화 전체가 그만큼 헐거워진다.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from app.core.llm.solar import solar_client

from ..blocks import (
    Block,
    ConceptBrief,
    clip_around,
    parse_response,
    retrieval_gap,
)
from ..retrieval_level import L1_RECALL, assess_cloze, assess_mcq, mix

# L1이 이 비율을 넘으면 재시도한다. 절반이 넘으면 "정의문 시험"이나 다름없다.
MAX_L1_RATIO = 0.5
# 재시도는 한 번만. 두 번째도 안 되면 재료 문제라 프롬프트로는 못 고친다.
MAX_RETRY = 1
# 누락 보충도 한 번만. 두 번 요청해도 안 나오면 그 개념은 설명에 재료가 없는 것이다.
MAX_FILL = 1
# 설명 본문을 프롬프트에 붙일 때의 상한.
MAX_EXPLANATION_CHARS = 1200


@dataclass(frozen=True)
class RetrievalResult:
    blocks: tuple[Block, ...]
    levels: dict[str, int]
    gap: tuple[str, ...]
    retried: bool = False
    # 보충으로 채운 개념. 게이트가 실제로 일했는지 보는 값이다
    filled: tuple[str, ...] = ()

    @property
    def l1_ratio(self) -> float:
        total = sum(self.levels.values())
        return self.levels.get("L1", 0) / total if total else 0.0


def _schema(concepts: list[ConceptBrief]) -> str:
    """응답 스키마 — **예시를 이 절의 개념으로 완성해서** 준다.

    ⚠️ 추상 자리(`"sentence": "…____…"`)를 주면 안 된다. 다섯 번 겪었다:
    모델이 그걸 그대로 내거나(필터에 걸려 인출 0개), 아예 빈칸 없는 평서문을
    낸다. 실측에서 `익스트림 프로그래밍` 절이 `____`가 없는 설명 문장 두 개를
    내놨다. **예시가 곧 출력**이므로 예시는 완성된 문항이어야 하고, 그러면
    베껴도 이 절의 유효한 문항이 된다.
    """
    first = concepts[0].key if concepts else "개념"
    second = concepts[1].key if len(concepts) > 1 else first
    options = [c.key for c in concepts[:4]] or [first]
    while len(options) < 3:
        options.append(f"{first} 아닌 것 {len(options)}")
    return f"""{{
  "cloze": [
    {{"kind": "상황", "sentence": "팀이 그런 방식으로 일하고 있다면 그것은 ____ 다.",
     "answer": "{first}", "concept": "{first}"}},
    {{"kind": "성질", "sentence": "{second}의 핵심은 ____ 에 있다.",
     "answer": "(설명이나 원문에 있는 말)", "concept": "{second}"}}
  ],
  "mcq": {{
    "question": "…에 해당하는 것은?",
    "options": {json.dumps(options, ensure_ascii=False)},
    "answer": "{first}",
    "explanation": "왜 그것인지"
  }}
}}"""


def build_prompt(
    section_title: str,
    concepts: list[ConceptBrief],
    explanation: str,
    source_text: str = "",
    feedback: str = "",
) -> str:
    """인출 문항만 만드는 프롬프트.

    설명 본문이 주 재료다. 개념 정의는 **이름을 확인하는 용도로만** 주고
    "옮겨 적지 마라"고 못박는다 — 그게 정의 되읽기의 원인이었다.
    """
    listing = "\n".join(f"- {c.key}" for c in concepts)
    keys = ", ".join(c.key for c in concepts)
    body = explanation.strip()[:MAX_EXPLANATION_CHARS]

    source_part = ""
    if source_text.strip():
        source_part = (
            "\n<교재 원문>\n"
            + clip_around(source_text.strip(), concepts)
            + "\n</교재 원문>\n"
        )

    fb = f"\n[이전 시도의 문제]\n{feedback}\n" if feedback else ""

    return f"""너는 **인출 문항만** 만드는 에이전트다. 설명은 이미 다 됐다.

학습자는 아래 설명을 방금 읽었다. 이 글을 덮고도 답할 수 있는 문항을 만들어라.

<학습자가 읽은 설명>
{body}
</학습자가 읽은 설명>
{source_part}
[이 절의 개념 {len(concepts)}개]
{listing}
{fb}
[규칙]
1. **빈칸 {len(concepts)}개 — 개념마다 하나씩.** 빠뜨리면 그 개념을 아는지
   판단할 수 없다. 문장 하나에 빈칸은 하나. concept에 어느 개념인지 적어라.

2. ★ **위 설명이나 개념 정의를 그대로 옮겨 적지 마라.**
   문장을 복사해 이름만 비우면 학습자는 개념이 아니라 **그 문장을 외웠는지**만
   확인받는다. 같은 내용을 **다른 말로** 다시 써라.

3. **kind를 넣고, 전부 같은 kind면 안 된다.**
   "정의"  개념의 뜻을 **다른 표현으로** 풀어 묻는다
   "상황"  그 개념이 실제로 벌어지는 **장면**을 묘사하고 이름을 묻는다
   "성질"  개념명을 문장에 두고 그 개념의 **성질·수치·순서**를 비운다.
           답은 개념명이 아니라 설명이나 원문에 있는 말이다
   "정의"는 절반을 넘기지 마라.

4. **조사나 서술어를 비우지 마라** — 문법으로 풀려 인출이 안 된다.
   (X) …는 이전 단계로 ____ 수 없다   → '돌아갈'은 문맥으로 나온다

5. **객관식 1개 — 개념들을 구별하는 문항.**
   빈칸이 "이걸 아는가"라면 객관식은 "이것들을 가를 수 있는가"다.
   **위 개념 중 최소 둘을 보기에 넣어라.** 한 개념만 묻는 문항은 빈칸과 중복이다.

아래 JSON 객체 하나만 출력한다(설명·코드펜스 금지):
{_schema(concepts)}

answer와 concept는 {keys} 중 하나를 정확히 쓴다(성질 유형의 answer는 예외)."""


def build_fill_prompt(
    section_title: str,
    concepts: list[ConceptBrief],
    missing: list[ConceptBrief],
    explanation: str,
    source_text: str = "",
) -> str:
    """**빠진 개념만** 다시 요청하는 프롬프트.

    전체 재생성이 아니라 보충인 이유: 나머지 문항은 멀쩡하다. 다시 만들면
    잘 나온 것까지 흔들리고, 실측에서 같은 절이 생성마다 빈칸 1개↔5개로
    출렁였다. 부족분만 받아 덧붙이면 결과가 단조 증가한다.

    범위를 좁혀서 주는 것도 요점이다 — 개념 10개 중 2개가 빠졌을 때 10개를
    다시 시키면 또 8개만 만든다. 2개만 시키면 2개를 만든다.
    """
    body = explanation.strip()[:MAX_EXPLANATION_CHARS]
    listing = "\n".join(f"- **{c.key}** — {c.definition}" for c in missing)
    others = ", ".join(c.key for c in concepts if c not in missing)

    source_part = ""
    if source_text.strip():
        source_part = (
            "\n<교재 원문>\n" + clip_around(source_text.strip(), missing) + "\n</교재 원문>\n"
        )

    examples = ",\n    ".join(
        f'{{"kind": "상황", "sentence": "그런 상황에서 쓰는 것이 ____ 다.", '
        f'"answer": "{c.key}", "concept": "{c.key}"}}'
        for c in missing
    )

    return f"""너는 인출 문항을 만드는 에이전트다. **빠진 것만 채운다.**

학습자는 아래 설명을 방금 읽었다.

<학습자가 읽은 설명>
{body}
</학습자가 읽은 설명>
{source_part}
[아직 한 번도 안 물어본 개념 {len(missing)}개]
{listing}

{f"※ {others} 는 이미 문항이 있다. **다시 만들지 마라.**" if others else ""}

[규칙]
1. **위 {len(missing)}개 개념에 대해 빈칸을 하나씩, 정확히 {len(missing)}개** 만든다.
   다른 개념 문항은 만들지 마라.
2. ★ **설명이나 정의를 그대로 옮겨 적지 마라.** 문장을 복사해 이름만 비우면
   학습자는 개념이 아니라 그 문장을 외웠는지만 확인받는다. 다른 말로 다시 써라.
3. **조사나 서술어를 비우지 마라** — 문법으로 풀려 인출이 안 된다.
4. 문장 하나에 빈칸은 하나. concept에 어느 개념인지 정확히 적는다.

아래 JSON 객체 하나만 출력한다(설명·코드펜스 금지):
{{
  "cloze": [
    {examples}
  ]
}}"""


async def _fill(
    section_title: str,
    concepts: list[ConceptBrief],
    gap: tuple[str, ...],
    explanation: str,
    source_text: str,
    grounds: str,
) -> list[Block]:
    """빠진 개념의 빈칸만 받아 온다. 실패하면 빈 목록 — 기존 문항은 안 건드린다."""
    missing = [c for c in concepts if c.key in gap]
    if not missing:
        return []
    prompt = build_fill_prompt(section_title, concepts, missing, explanation, source_text)
    try:
        raw = await solar_client.generate(
            prompt, response_format={"type": "json_object"}, temperature=0.4
        )
    except Exception as e:  # noqa: BLE001
        print(f"[retrieval] 보충 실패 {section_title}: {type(e).__name__}: {e}")
        return []
    # 빠진 개념 것만 받는다. 이미 있는 개념을 또 만들어 오면 버린다 —
    # 안 그러면 한 개념에 빈칸 둘이 붙어 다른 개념 자리를 먹는다.
    want = set(gap)
    return [
        b
        for b in parse_response(raw, concepts, grounds)
        if b.type == "cloze" and set(b.concept_keys) & want
    ]


def _levels_of(blocks: list[Block], concepts: list[ConceptBrief], source: str) -> list[int]:
    defs = {c.key: c.definition for c in concepts}
    keys = [c.key for c in concepts]
    out: list[int] = []
    for b in blocks:
        if b.type == "cloze":
            key = b.concept_keys[0] if len(b.concept_keys) == 1 else ""
            out.append(assess_cloze(b.content["sentence"], defs.get(key, ""), source))
        elif b.type == "mcq":
            out.append(assess_mcq(b.content["options"], keys))
    return out


def _feedback(blocks: list[Block], levels: list[int]) -> str:
    """어느 문항이 왜 걸렸는지 짚는다. 뭉뚱그리면 모델이 못 고친다."""
    lines: list[str] = []
    idx = 0
    for b in blocks:
        if b.type not in ("cloze", "mcq"):
            continue
        if idx < len(levels) and levels[idx] == L1_RECALL and b.type == "cloze":
            lines.append(f'  · "{b.content["sentence"][:50]}" — 설명 문장을 그대로 옮겼다')
        idx += 1
    if not lines:
        return ""
    return (
        "아래 문항이 설명·정의를 그대로 옮겨 적었다. **같은 내용을 다른 말로** 다시 써라.\n"
        + "\n".join(lines[:4])
    )


async def generate(
    section_title: str,
    concepts: list[ConceptBrief],
    explanation: str,
    source_text: str = "",
) -> RetrievalResult:
    """인출 문항을 만들고 **스스로 재서** 품질은 다시 만들고 누락은 채운다."""
    best: RetrievalResult | None = None
    feedback = ""
    grounds = "\n".join(x for x in (source_text, explanation) if x)

    for attempt in range(MAX_RETRY + 1):
        prompt = build_prompt(section_title, concepts, explanation, source_text, feedback)
        try:
            raw = await solar_client.generate(
                prompt, response_format={"type": "json_object"}, temperature=0.4
            )
        except Exception as e:  # noqa: BLE001
            print(f"[retrieval] 생성 실패 {section_title}: {type(e).__name__}: {e}")
            break

        # ★ 근거에 **설명 본문**을 넣는다. 인출은 방금 읽은 글에서 꺼내는 것이므로
        #   설명이 1차 근거다. 원문만 보면 "성질" 유형이 전부 걸린다 —
        #   실측에서 답이 `계획부터 유지보수까지`·`위에서 아래로`처럼 개념명이
        #   아닌 것들이 다 잘려 6절 중 4절이 빈칸 0개가 됐다.
        blocks = [
            b for b in parse_response(raw, concepts, grounds) if b.type in ("cloze", "mcq")
        ]
        levels = _levels_of(blocks, concepts, source_text)
        result = RetrievalResult(
            blocks=tuple(blocks),
            levels=mix(levels),
            gap=tuple(retrieval_gap(blocks, concepts)),
            retried=attempt > 0,
        )
        # 문항이 더 많거나, 같은 수라면 L1이 적은 쪽을 고른다.
        # 개선하려다 문항을 잃으면 손해다.
        if best is None or (
            len(result.blocks) > len(best.blocks)
            or (len(result.blocks) == len(best.blocks) and result.l1_ratio < best.l1_ratio)
        ):
            best = result
        if not blocks or result.l1_ratio <= MAX_L1_RATIO:
            break
        feedback = _feedback(blocks, levels)
        if not feedback:
            break

    if best is None or not best.blocks:
        return best or RetrievalResult(blocks=(), levels=mix([]), gap=())

    # ── 누락 보충 ──────────────────────────────────────────────────
    # 여기가 없어서 "개념마다 하나씩"이 프롬프트의 부탁으로만 남아 있었다.
    # 실측 81% → 아래 참조. 덧붙이기라 결과가 나빠질 수 없다.
    for _ in range(MAX_FILL):
        if not best.gap:
            break
        added = await _fill(
            section_title, concepts, best.gap, explanation, source_text, grounds
        )
        if not added:
            break  # 두 번 시켜도 같다. 그 개념은 설명에 재료가 없는 것이다
        merged = list(best.blocks) + added
        # 객관식이 뒤에 오도록 — 화면이 빈칸 먼저 보여주고 객관식으로 닫는다
        merged.sort(key=lambda b: b.type == "mcq")
        best = RetrievalResult(
            blocks=tuple(merged),
            levels=mix(_levels_of(merged, concepts, source_text)),
            gap=tuple(retrieval_gap(merged, concepts)),
            retried=best.retried,
            filled=best.filled + tuple(k for b in added for k in b.concept_keys),
        )

    return best
