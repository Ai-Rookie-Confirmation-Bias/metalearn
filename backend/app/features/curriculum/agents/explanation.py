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

from ..blocks import Block, ConceptBrief, clip_around, coverage, parse_response

_SCHEMA = """{
  "explanation": "설명 본문 (여러 문단 가능)",
  "analogy": "비유 — 쓰지 않을 거면 JSON null (문자열 \\"null\\" 아님)"
}"""


@dataclass(frozen=True)
class ExplanationResult:
    blocks: tuple[Block, ...]
    covered: int
    missing: tuple[str, ...]

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

    return f"""너는 학습 콘텐츠를 쓰는 에이전트다. 아래 개념들을 한 묶음으로 설명하라.
문항은 만들지 마라 — 다른 에이전트가 맡는다.

[절] {section_title}
[개념 {len(concepts)}개]
{listing}
{source_part}
[규칙]
1. **설명 본문**: 위 개념 정의(와 원문)에 있는 사실만 쓴다. 없는 사실을 지어내지 마라.
   단 **설명하는 방식·순서·분량은 자유**다.
2. **{len(concepts)}개 개념을 모두 다뤄라.** 하나도 빠뜨리지 마라.
   이들은 서로 관련이 있어 한 묶음이 됐으므로 **연결해서** 설명하라.
   따로따로 나열하지 마라.
3. **비유**: 이해를 돕는 장치이므로 **원문 밖에서 가져와도 된다.** 일상 경험에
   빗대라. 쓰지 않을 거면 JSON null을 넣어라.
4. 학습자가 읽을 글이다. "정의에 따르면" 같은 메타 표현은 쓰지 마라.
{profile_part}
아래 JSON 객체 하나만 출력한다(설명·코드펜스 금지):
{_SCHEMA}"""


async def generate(
    section_title: str,
    concepts: list[ConceptBrief],
    profile_block: str = "",
    source_text: str = "",
) -> ExplanationResult:
    prompt = build_prompt(section_title, concepts, profile_block, source_text)
    try:
        raw = await solar_client.generate(
            prompt, response_format={"type": "json_object"}, temperature=0.3
        )
    except Exception as e:  # noqa: BLE001
        print(f"[explanation] 생성 실패 {section_title}: {type(e).__name__}: {e}")
        return ExplanationResult(blocks=(), covered=0, missing=())

    blocks = [
        b for b in parse_response(raw, concepts, source_text) if b.type in ("concept", "analogy")
    ]
    covered, missing = coverage(blocks, concepts)
    return ExplanationResult(blocks=tuple(blocks), covered=covered, missing=tuple(missing))
