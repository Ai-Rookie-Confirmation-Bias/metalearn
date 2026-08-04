"""[순수로직] 절 하나 → 학습 블록 프롬프트·파싱.

LLM 호출은 하지 않는다(호출측이 LLMClient로 한다). 프롬프트를 만들고 응답을
검증하는 것까지만 맡아 테스트가 가능하게 둔다.

## 무엇을 만드나

절(개념 5~10개)마다 블록 묶음을 만든다.
    설명(concept)  → 읽기
    비유(analogy)  → 읽기, 성향에 따라 생략
    빈칸(cloze)    → **인출**
"읽게 하지 않고 꺼내게 한다"가 서비스 정의이므로 인출이 반드시 붙는다.

## 왜 개념 정의가 주 재료인가

원문(조각)은 평균 3,438자인데 개념별로 자르는 데 실패했다(실측 53%,
구간 중앙 50자). 2단 조판 PDF를 텍스트로 뽑은 것이라 항목 번호와 제목이
떨어지고 본문 중간에 다른 항목이 끼어든다 — 완전 복원은 무리다.

그런데 파싱이 개념마다 **정제된 정의**를 이미 준다:
    HIPO — 하향식 소프트웨어 개발을 위한 문서화 도구로 기호, 도표 등을 사용
이게 원문에서 뽑아낸 것이므로 근거로서도 유효하고, 절 하나가 200~300자로
생성에 딱 맞는 크기다. 원문은 **있으면 보조로 붙이고** 근거 표시에 쓴다.

## 비유는 왜 별도 필드인가

1차 실험에서 5조합이 전부 같은 글이 나왔다. "원문에 있는 사실만 써라"와
"비유를 먼저 놓아라"가 프롬프트 안에서 충돌해 모델이 안전한 쪽(원문 복창)을
택했기 때문이다. **비유는 본질적으로 원문 밖 정보**이므로 설명 본문과 분리해
"여기서는 원문 밖을 써도 된다"고 명시해야 성향이 작동한다.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

# ── 인출 밀도 ────────────────────────────────────────────────────────
# 빈칸은 **개념마다** 하나. 절 기준으로 잡으면 단위를 바꿀 때 인출 수가 따라
# 바뀌고, 실측에서 절당 2개 = 개념당 0.27개가 되어 **개념 넷 중 셋이 한 번도
# 안 꺼내졌다.** 그러면 그 개념을 아는지 모르는지 판단할 데이터가 없다.
CLOZE_PER_CONCEPT = 1
# 객관식은 **절마다** 하나. 빈칸과 목적이 다르다:
#   빈칸   = 회상(recall)      "Belady란?"           → 개념 하나를 꺼낼 수 있나
#   객관식 = 구별(discrimination) "Belady vs 스래싱"  → 개념 사이를 가를 수 있나
# 구별은 여러 개념이 있어야 성립하므로 절 단위가 자연스럽다. 개념마다 만들면
# 빈칸과 중복되고 문항이 2배가 된다(754개 · 6.3시간).
MCQ_PER_SECTION = 1
# 원문을 붙일 때의 상한. 넘으면 요약되기 시작한다(문항 생성 실측 근거).
MAX_SOURCE_CHARS = 1500


@dataclass(frozen=True)
class ConceptBrief:
    """생성에 넘기는 개념 한 줄."""

    key: str
    definition: str


@dataclass(frozen=True)
class Block:
    type: str  # concept | analogy | cloze
    content: dict
    # 이 블록이 어느 개념에서 나왔는지 — 커버리지 측정과 근거 추적에 쓴다.
    concept_keys: tuple[str, ...] = ()


# ⚠️ 스키마의 placeholder를 모델이 그대로 베끼는 사고가 있었다(실측: 빈칸 문장이
# "____ 가 들어갈 자리를 포함한 문장"으로 나왔다). 예시를 **실제 문항 모양**으로
# 써두면 베껴도 형태가 유지된다.
_SCHEMA = """{
  "explanation": "설명 본문 (여러 문단 가능)",
  "analogy": "비유 — 쓰지 않을 거면 JSON null (문자열 \\"null\\" 아님)",
  "cloze": [
    {"sentence": "이전 단계로 돌아갈 수 없는 고전적 생명주기 모형을 ____ 이라 한다.",
     "answer": "폭포수 모형", "concept": "폭포수 모형"}
  ],
  "mcq": {
    "question": "다음 설명에 해당하는 것은?",
    "options": ["보기1", "보기2", "보기3", "보기4"],
    "answer": "보기1",
    "explanation": "왜 그것인지"
  }
}"""

# 스키마 예시를 베낀 흔적. 이런 문장은 문항이 아니다.
_TEMPLATE_MARKERS = ("들어갈 자리", "포함한 문장", "설명 본문", "개념명")


def build_prompt(
    section_title: str,
    concepts: list[ConceptBrief],
    profile_block: str = "",
    source_text: str = "",
) -> str:
    """절 하나의 학습 블록을 만드는 프롬프트.

    profile_block은 profile.prompt_block()의 출력. 비어 있으면 중립 생성이다
    (측정이 부족하면 아무 지시도 하지 않는다는 원칙).
    """
    listing = "\n".join(f"- **{c.key}** — {c.definition}" for c in concepts)
    keys = ", ".join(c.key for c in concepts)

    source_part = ""
    if source_text.strip():
        clipped = source_text.strip()[:MAX_SOURCE_CHARS]
        source_part = (
            f"\n<교재 원문 (참고)>\n{clipped}\n</교재 원문>\n"
            "※ 원문은 PDF 추출본이라 공백·줄바꿈이 뒤틀려 있고 항목 번호나 잡음이\n"
            "  섞여 있을 수 있다. 읽어서 이해하되 잡음은 버려라.\n"
        )

    profile_part = f"\n{profile_block}\n" if profile_block else "\n"

    return f"""너는 학습 콘텐츠를 쓰는 에이전트다. 아래 개념들을 한 묶음으로 설명하라.

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
4. **빈칸 {len(concepts)}개 — 개념마다 하나씩.** 빠뜨리면 그 개념을 아는지
   판단할 수 없다. 설명을 덮고도 답할 수 있어야 하므로 **핵심 용어를 비워라.**
   조사나 서술어를 비우면 문법으로 풀려 인출이 되지 않는다.
   (X) 폭포수 모형은 이전 단계로 ____ 수 없다   → '돌아갈'은 문맥으로 나온다
   (O) 이전 단계로 돌아갈 수 없는 모형을 ____ 이라 한다   → 개념을 꺼내야 한다
   문장 하나에 빈칸은 하나만. concept에 어느 개념인지 정확히 적어라.
5. **객관식 1개 — 개념들을 구별하는 문항.** 빈칸이 "이걸 아는가"라면 객관식은
   "이것들을 가를 수 있는가"다. **위 개념 중 여럿을 보기로 넣어** 헷갈리는
   지점을 묻어라. 한 개념만 묻는 문항은 빈칸과 중복이니 만들지 마라.
6. 학습자가 읽을 글이다. "정의에 따르면" 같은 메타 표현은 쓰지 마라.
{profile_part}
아래 JSON 객체 하나만 출력한다(설명·코드펜스 금지):
{_SCHEMA}

concept 필드에는 {keys} 중 하나를 정확히 써라."""


def _clean_optional(value: object) -> str:
    """모델이 null을 문자열 "null"로 보내는 사고를 흡수한다(실측)."""
    if not isinstance(value, str):
        return ""
    text = value.strip()
    return "" if text.lower() in {"null", "none", "n/a", ""} else text


def parse_response(raw: str, concepts: list[ConceptBrief]) -> list[Block]:
    """LLM 응답 → 블록 목록. 깨진 항목은 버리고 나머지는 살린다.

    부가 항목(비유·빈칸) 하나가 깨졌다고 설명 본문까지 잃으면 손해가 크다.
    """
    try:
        data = json.loads(raw[raw.find("{") : raw.rfind("}") + 1])
    except (json.JSONDecodeError, ValueError):
        return []

    valid_keys = {c.key for c in concepts}
    all_keys = tuple(c.key for c in concepts)
    blocks: list[Block] = []

    explanation = _clean_optional(data.get("explanation"))
    if explanation:
        blocks.append(
            Block("concept", {"text": explanation}, concept_keys=all_keys)
        )

    analogy = _clean_optional(data.get("analogy"))
    if analogy:
        # 비유는 사실이 아니라 이해 장치다. 화면에서 그렇게 보이도록 라벨을 강제한다.
        blocks.append(
            Block("analogy", {"text": analogy, "label": "비유"}, concept_keys=all_keys)
        )

    for item in data.get("cloze") or []:
        if not isinstance(item, dict):
            continue
        sentence = _clean_optional(item.get("sentence"))
        answer = _clean_optional(item.get("answer"))
        # 빈칸 표시가 없거나 정답이 문장에 그대로 남아 있으면 문항이 아니다.
        if not sentence or not answer or "____" not in sentence:
            continue
        if answer in sentence.replace("____", ""):
            continue
        # 스키마 예시를 베낀 문장 차단(실측 사고).
        if any(m in sentence for m in _TEMPLATE_MARKERS):
            continue
        # 문맥 없이 빈칸만 있으면 답을 특정할 수 없다.
        if len(sentence.replace("____", "").strip()) < 10:
            continue
        concept = item.get("concept")
        concept = concept if concept in valid_keys else None
        blocks.append(
            Block(
                "cloze",
                {"sentence": sentence, "answer": answer},
                concept_keys=(concept,) if concept else all_keys,
            )
        )

    mcq = data.get("mcq")
    if isinstance(mcq, dict):
        question = _clean_optional(mcq.get("question"))
        options = [
            _clean_optional(o) for o in (mcq.get("options") or []) if _clean_optional(o)
        ]
        answer = _clean_optional(mcq.get("answer"))
        # 정답이 보기에 없거나 보기가 부족하면 문항이 아니다.
        ok = (
            question
            and len(options) >= 3
            and answer in options
            and len(set(options)) == len(options)
            and not any(m in question for m in _TEMPLATE_MARKERS)
        )
        if ok:
            blocks.append(
                Block(
                    "mcq",
                    {
                        "question": question,
                        "options": options,
                        "answer": answer,
                        "explanation": _clean_optional(mcq.get("explanation")),
                    },
                    concept_keys=all_keys,
                )
            )

    return blocks


def retrieval_gap(blocks: list[Block], concepts: list[ConceptBrief]) -> list[str]:
    """빈칸이 한 번도 안 걸린 개념 — **인출 누락**.

    설명에 언급되기만 하고 꺼내보지 않은 개념은 "안다/모른다"를 판정할 수
    없다. 커리큘럼을 개인화할 데이터가 그만큼 비는 것이므로 커버리지와 별개로
    따로 센다.
    """
    asked = {k for b in blocks if b.type == "cloze" for k in b.concept_keys}
    return [c.key for c in concepts if c.key not in asked]


# 토큰 끝에 붙는 조사. 개념명 "XP의 핵심 가치"의 "XP의"가 본문의
# "XP(eXtreme Programming)의"와 안 맞는 문제를 푼다.
_PARTICLES = "의은는이가을를와과도로에서"


def _variants(token: str) -> list[str]:
    """토큰과 조사를 뗀 형태. 2글자짜리는 자르지 않는다(한 글자가 되면 오탐)."""
    out = [token]
    if len(token) > 2 and token[-1] in _PARTICLES:
        out.append(token[:-1])
    return out


# 개념명의 괄호 병기. `목 오브젝트 (Mock Object)` / `DRM(디지털 저작권 관리)`
_PAREN = re.compile(r"\s*[(（]([^)）]*)[)）]\s*")


def aliases(key: str) -> list[str]:
    """개념명의 표기 후보. 괄호 병기를 **따로 떼어** 둘 다 후보로 삼는다.

    실측 사고: 개념명이 `목 오브젝트 (Mock Object)`인데 본문은 `목 오브젝트`라고만
    써서 **넷 다 나와 있는 설명이 `언급 0/4`로 찍혔다.** 토큰으로 쪼개면
    `(Mock` `Object)`가 본문에 없어 70% 문턱을 못 넘기 때문이다.

    교재도 설명도 한쪽 표기만 쓴다. 둘 다 요구하면 정상 문장이 누락이 된다.
    괄호 병기 개념은 실측에서 필기 16%·실기 15%로 적지 않다.

        "목 오브젝트 (Mock Object)"  →  ["목 오브젝트", "Mock Object"]
        "DRM(디지털 저작권 관리)"     →  ["DRM", "디지털 저작권 관리"]
    """
    # 원형을 먼저 둔다 — `Python input() 함수`처럼 괄호가 병기가 아니라
    # 이름의 일부인 경우가 있다. 떼어내면 원문과 안 맞는다.
    out = [key.strip()]
    outer = _PAREN.sub(" ", key).strip()
    if len(outer) >= 2:
        out.append(outer)
    # 병기 자체(`Mock Object`). 한 글자짜리는 노이즈라 버린다.
    out += [a.strip() for a in _PAREN.findall(key) if len(a.strip()) >= 2]
    return [a for a in dict.fromkeys(out) if a]


def _mentions_one(text: str, key: str) -> bool:
    if key.replace(" ", "") in text.replace(" ", ""):
        return True
    tokens = [t for t in key.split() if len(t) >= 2]
    if not tokens:
        return key in text
    hit = sum(1 for t in tokens if any(v in text for v in _variants(t)))
    return hit / len(tokens) >= 0.7


def _mentions(text: str, key: str) -> bool:
    """개념명이 본문에 언급됐는가 — **정확 일치로 세면 안 된다.**

    실측 사고: 개념명 "XP의 핵심 가치"를 본문이 "XP(eXtreme Programming)의 핵심
    가치"로 썼는데 누락으로 셌다. "애자일 개발 4가지 핵심 가치"도 본문의
    "애자일 개발 자체의 4가지 핵심 가치"와 안 맞았다. 정상 문장인데 손실로
    잡히면 **커버리지 숫자 자체를 못 믿게 된다.**

    개념명을 토큰으로 쪼개 조사를 떼고, 대부분이 나타나면 언급으로 본다.
    표기 후보(`aliases`) 중 **하나라도** 맞으면 언급으로 친다.
    """
    return any(_mentions_one(text, a) for a in aliases(key))


def coverage(blocks: list[Block], concepts: list[ConceptBrief]) -> tuple[int, list[str]]:
    """설명 본문이 개념을 몇 개나 실제로 언급했는지.

    "빠뜨리지 마라"는 지시만으로는 안 지켜진다(문항 생성 실측). 숫자로 확인해야
    손실을 관리할 수 있다.
    """
    text = " ".join(
        b.content.get("text", "") for b in blocks if b.type in {"concept", "analogy"}
    )
    missing = [c.key for c in concepts if not _mentions(text, c.key)]
    return len(concepts) - len(missing), missing
