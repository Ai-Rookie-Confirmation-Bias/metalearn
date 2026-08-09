"""설명 에이전트 — 절 → 설명 + 비유.

인출은 안 만든다. 한 프롬프트가 둘 다 하면 지시가 서로 밀어낸다(실측: 빈칸 유형을
자세히 쓸수록 설명 규칙이 묻혔다). 여기는 **읽을 것**만 맡는다.

## 왜 개념 정의가 주 재료인가

원문(조각)은 절별로 잘라도 중앙값 362자이고, 개념별로 정확히 자르는 데 실패했다.
그런데 파싱이 개념마다 **정제된 정의**를 준다. 원문에서 뽑은 것이라 근거로도
유효하고 절 하나가 200~300자로 생성에 맞는 크기다. 원문은 보조로 붙인다.

## 비유는 왜 별도 필드인가

1차 실험에서 성향 조합이 전부 같은 글이 나왔다. "원문에 있는 사실만 써라"와
"비유를 먼저 놓아라"가 프롬프트 안에서 충돌해 모델이 안전한 쪽(원문 복창)을
택했기 때문이다. **비유는 본질적으로 원문 밖 정보**이므로 분리해서
"여기서는 원문 밖을 써도 된다"고 명시해야 성향이 작동한다.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.core.llm.solar import solar_client

from ..blocks import (
    Block,
    ConceptBrief,
    _mentions,
    clip_around,
    coverage,
    parse_response,
)

_SCHEMA = """{
  "explanation": "설명 본문 (여러 문단 가능)",
  "analogy": "비유 — 쓰지 않을 거면 JSON null (문자열 \\"null\\" 아님)"
}"""

# 약점을 짚을 때만 붙는 필드. 본문(`explanation`)과 분리한다 —
# 비유를 분리한 것과 같은 이유이고, 실측으로도 본문 안 지시는 안 먹혔다.
_SCHEMA_WITH_TIE_IN = """{
  "explanation": "설명 본문 (여러 문단 가능)",
  "analogy": "비유 — 쓰지 않을 거면 JSON null (문자열 \\"null\\" 아님)",
  "tie_in": "최근 틀린 개념을 지금 배우는 것과 엮어 짚는 **한 문단** — 엮을 게 없으면 JSON null",
  "tie_in_more": "펼쳐야 보이는 다시 설명. 그 개념 하나를 처음 배우듯 — tie_in이 null이면 null"
}"""

# 화면에서 이 문단에 붙는 라벨.
TIE_IN_LABEL = "여기서 잠깐"


@dataclass(frozen=True)
class ExplanationResult:
    blocks: tuple[Block, ...]
    covered: int
    missing: tuple[str, ...]
    # 실제로 본문에서 엮은 약점 개념. **요청한 것이 아니라 들어간 것**이다.
    tied_in: tuple[str, ...] = ()

    @property
    def text(self) -> str:
        return next((b.content["text"] for b in self.blocks if b.type == "concept"), "")

    @property
    def ok(self) -> bool:
        return bool(self.text)


def build_prompt(
    section_title: str,
    concepts: list[ConceptBrief],
    profile_block: str = "",
    source_text: str = "",
    weak_concepts: tuple[str, ...] = (),
    mode_block: str = "",
    style_last: bool = False,
) -> str:
    listing = "\n".join(f"- **{c.key}** — {c.definition}" for c in concepts)

    source_part = ""
    if source_text.strip():
        source_part = (
            f"\n<교재 원문 (참고)>\n{clip_around(source_text.strip(), concepts)}\n</교재 원문>\n"
            "※ 원문은 PDF 추출본이라 공백·줄바꿈이 뒤틀려 있고 항목 번호나 잡음이\n"
            "  섞여 있을 수 있다. 읽어서 이해하되 잡음은 버려라.\n"
        )
    profile_part = f"\n{profile_block}\n" if profile_block else "\n"
    # ⚠️ **분량이 성향보다 뒤에 온다.** 순서가 곧 우선순위다 — 둘이 부딪히는
    #    자리가 실제로 있다(성향 "비유를 먼저" vs compressed "비유 금지").
    #    바꾸면 압축 단원에 비유가 다시 들어온다. 근거는 `planner.mode_block`.
    mode_part = f"\n{mode_block}\n" if mode_block else ""

    # `style_last`면 뒤집는다. **재지 않고 목표만으로 압축한 자리**가 그렇다 —
    # 거기서는 형식이 학습자가 직접 고른 값이라 분량에 밀리면 안 된다.
    #
    # ⚠️ **이것만으로는 아무것도 안 바뀌었다.** 비유가 안 나오던 문제를 이걸로
    #    고치려다 실패했고(실측: 뒤집기 전후 둘 다 비유 0개), 결국 성향 지시
    #    자체를 세게 쓰고서야(`profile._ENFORCE`) 들어왔다. 순서는 우선순위를
    #    맞추는 장치일 뿐 **모델을 움직이는 힘은 아니다.** 여기에 기대지 마라.
    if style_last:
        profile_part, mode_part = mode_part or "\n", profile_part

    # 이 학습자가 최근 틀린 개념 중 이 절과 이어지는 것. 없으면 아무 말도 안 한다.
    weak_part = ""
    if weak_concepts:
        names = " · ".join(f"**{k}**" for k in weak_concepts)
        weak_part = f"""5. **tie_in**: 이 학습자가 최근 {names}을(를) 틀렸다.
   이 절 내용과 **이어지는 지점**을 찾아 한 문단으로 짚어라. 지금 배우는 것과
   엮어서 설명해야 붙는다(따로 떼어 다시 설명하는 게 아니다).
   개념 이름을 그대로 써라 — 학습자가 "그때 그거"라고 알아봐야 한다.
   ⚠️ 이어지는 지점이 정말 없으면 JSON null을 넣어라. 억지로 엮으면 방해가 된다.

6. **tie_in_more**: 위 한 문단을 읽고도 막히는 사람이 **펼쳐서** 보는 글이다.
   거기서는 {names}을(를) **처음 배우듯** 설명해라 — 이번엔 지금 개념과 엮지
   말고 그 개념 자체를 세워라. 두세 문단.
   본문에서 이미 한 말을 옮겨 적지 마라. 펼쳤는데 같은 글이면 안 펼친 것과 같다.
   ⚠️ tie_in이 null이면 여기도 null이다.
"""

    return f"""너는 학습 콘텐츠를 쓰는 에이전트다. 아래 개념들을 한 화면 분량으로 설명하라.
문항은 만들지 마라 — 다른 에이전트가 맡는다.

[화면] {section_title}
[개념 {len(concepts)}개]
{listing}
{source_part}
[규칙]
1. **설명 본문**: 위 개념 정의(와 원문)에 있는 사실만 쓴다. 없는 사실을 지어내지 마라.
   단 **설명하는 방식·순서·분량은 자유**다.
2. **{len(concepts)}개 개념을 모두 다뤄라.** 하나도 빠뜨리지 마라.
   개념들은 원문에서 가까이 있어 한 화면에 담겼을 뿐이다 — **관련이 있다고 단정하지 마라.**
   연결점이 있으면 이어서 쓰고, 없으면 각각 명확히 설명하라. 없는 연결을 지어내지 마라.
3. **비유**: 이해를 돕는 장치이므로 **원문 밖에서 가져와도 된다.** 일상 경험에
   빗대라. 쓰지 않을 거면 JSON null을 넣어라.
4. 학습자가 읽을 글이다. "정의에 따르면" 같은 메타 표현은 쓰지 마라.
{weak_part}{profile_part}{mode_part}
아래 JSON 객체 하나만 출력한다(설명·코드펜스 금지):
{_SCHEMA_WITH_TIE_IN if weak_concepts else _SCHEMA}"""


async def generate(
    section_title: str,
    concepts: list[ConceptBrief],
    profile_block: str = "",
    source_text: str = "",
    weak_concepts: tuple[str, ...] = (),
    mode_block: str = "",
    style_last: bool = False,
) -> ExplanationResult:
    prompt = build_prompt(
        section_title,
        concepts,
        profile_block,
        source_text,
        weak_concepts,
        mode_block,
        style_last,
    )
    try:
        raw = await solar_client.generate(
            prompt, response_format={"type": "json_object"}, temperature=0.3
        )
    except Exception as e:  # noqa: BLE001
        print(f"[explanation] 생성 실패 {section_title}: {type(e).__name__}: {e}")
        return ExplanationResult(blocks=(), covered=0, missing=())

    blocks = [
        b
        for b in parse_response(raw, concepts, source_text)
        if b.type in ("concept", "analogy", "tie_in")
    ]
    hit = tied_in(blocks, weak_concepts)
    if weak_concepts and not hit:
        # 엮을 게 없다고 판단했거나 개념명을 안 썼다. 문단은 버린다 —
        # 남겨두면 "약점을 짚었다"고 화면이 말하는데 정작 뭘 짚었는지 없다.
        blocks = [b for b in blocks if b.type != "tie_in"]

    # 커버리지는 tie_in을 빼고 센다 — 그 문단은 **지난 개념**을 짚는 자리라,
    # 거기서 이 절 개념이 스쳤다고 "설명했다"로 세면 손실이 가려진다.
    covered, missing = coverage([b for b in blocks if b.type != "tie_in"], concepts)
    return ExplanationResult(
        blocks=tuple(blocks), covered=covered, missing=tuple(missing), tied_in=hit
    )


def tied_in(blocks: list[Block], weak_concepts: tuple[str, ...]) -> tuple[str, ...]:
    """**실제로** 엮인 약점 개념.

    요청했다고 반영된 게 아니다. 모델은 "엮을 게 없으면 null"을 따를 수도,
    문단은 쓰면서 개념 이름은 안 쓸 수도 있다. 화면의 ⚡는 여기서 나온 것만 보고
    띄운다 — **이유만 있고 본문이 그대로면 거짓말**이기 때문이다.

    문단과 개념명이 **둘 다** 있어야 인정한다. 개념명이 없으면 학습자가 "그때
    그거"라고 알아볼 수 없어서 짚어준 게 아니다.
    """
    text = next((b.content["text"] for b in blocks if b.type == "tie_in"), "")
    if not weak_concepts or not text:
        return ()
    return tuple(k for k in weak_concepts if _mentions(text, k))
