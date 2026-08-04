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

## 자기 품질을 자기가 잰다

`retrieval_level`이 판정한다. 시키는 쪽과 재는 쪽이 같으면 자기 채점이 되므로
판정은 순수 로직에 두고 여기서 호출만 한다. L1(정의 되읽기)이 과하면 **어느
문항이 왜 걸렸는지 붙여서 한 번 재시도**한다.

⚠️ 재시도 결과가 더 나쁘면 처음 것을 쓴다. 개선하려다 문항을 잃으면 손해다.
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
# 설명 본문을 프롬프트에 붙일 때의 상한.
MAX_EXPLANATION_CHARS = 1200


@dataclass(frozen=True)
class RetrievalResult:
    blocks: tuple[Block, ...]
    levels: dict[str, int]
    gap: tuple[str, ...]
    retried: bool = False

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
    """인출 문항을 만들고 **스스로 재서** 필요하면 한 번 다시 만든다."""
    best: RetrievalResult | None = None
    feedback = ""

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
        grounds = "\n".join(x for x in (source_text, explanation) if x)
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

    return best or RetrievalResult(blocks=(), levels=mix([]), gap=())
