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

from .excerpt import aliases, category_words, normalize_spaces, source_aliases

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


def _gist(definition: str, limit: int = 44) -> str:
    """정의문에서 예시 문장에 쓸 짧은 조각. 문장 끝 어미는 떼고 이어 붙일 수 있게."""
    d = re.split(r"[.。\n]", definition.strip())[0].strip()
    d = re.sub(r"(이다|입니다|한다|합니다|임|함)$", "", d).strip()
    return (d[:limit].rstrip() or "그런 성질을 가진")


def _schema_for(concepts: list[ConceptBrief]) -> str:
    """응답 스키마 — **예시를 이 절의 개념으로 만든다.**

    모델은 예시를 베낀다. 세 번 겪었다:
      ① placeholder를 그대로  — "____ 가 들어갈 자리를 포함한 문장"
      ② 고쳤더니 구체 예시를  — `접근 통제 기술` 절에 "폭포수 모형" 문항
      ③ 원문이 짧은 절일수록 심하다. 재료가 없으니 예시에 기댄다

    ②를 `_grounded`로 막았더니 이번엔 **인출이 0개인 절**이 절반이 됐다. 막을수록
    비는 것이다. 그래서 막는 대신 **베껴도 무해하게** 만든다 — 예시가 이 절의
    개념이면 그대로 베껴도 이 절 문항이다.

    `_grounded`는 그대로 둔다. 다른 절 개념을 끌어오는 경우까지는 막아야 한다.
    """
    first = concepts[0].key if concepts else "개념"
    second = concepts[1].key if len(concepts) > 1 else first
    # 예시는 **완성된 문장**이어야 한다. 빈칸을 `(…)`로 남겨두면 모델이 그대로
    # 내고 필터에 걸려 **인출이 0개**가 된다(실측). 개념 정의로 문장을 만들면
    # 베껴도 이 절의 유효한 문항이고, 안 베끼면 더 나아진다.
    d1 = _gist(concepts[0].definition) if concepts else "그런 성질을 가진 것"
    d2 = _gist(concepts[1].definition) if len(concepts) > 1 else d1
    options = [c.key for c in concepts[:4]] or [first]
    while len(options) < 3:  # 보기가 모자라면 스키마가 규칙과 어긋난다
        options.append(f"{first} 아닌 것 {len(options)}")
    return f"""{{
  "explanation": "설명 본문 (여러 문단 가능)",
  "analogy": "비유 — 쓰지 않을 거면 JSON null (문자열 \\"null\\" 아님)",
  "cloze": [
    {{"kind": "정의", "sentence": "{d1} 것을 ____ 이라 한다.",
     "answer": "{first}", "concept": "{first}"}},
    {{"kind": "상황", "sentence": "어떤 팀이 {d2} 방식으로 일하고 있다면 그것은 ____ 다.",
     "answer": "{second}", "concept": "{second}"}}
  ],
  "mcq": {{
    "question": "(…{first}만 해당하는 설명…) 에 해당하는 것은?",
    "options": {json.dumps(options, ensure_ascii=False)},
    "answer": "{first}",
    "explanation": "왜 그것인지"
  }}
}}"""

# 스키마 예시를 베낀 흔적. 이런 문장은 문항이 아니다.
#
# ⚠️ **예시에 빈 자리를 남기면 안 된다.** `(…)`로 두면 모델이 그대로 내고 여기서
#    전부 걸려 **인출이 0개**가 된다(실측). 예시는 `_schema_for`가 절 개념으로
#    완성된 문장을 만들어 준다 — 베껴도 유효하고, 안 베끼면 더 나아진다.
_TEMPLATE_MARKERS = (
    "들어갈 자리",
    "포함한 문장",
    "설명 본문",
    "개념명",
    "다음 설명에 해당하는 것은",
    "보기1",
    "(…",
)


def _sq(text: str) -> str:
    return re.sub(r"\s+", "", normalize_spaces(text))


def clip_around(
    source: str, concepts: list[ConceptBrief], budget: int = MAX_SOURCE_CHARS
) -> str:
    """원문을 **개념이 나오는 자리 기준으로** 자른다. 앞에서 자르지 않는다.

    앞에서 budget만큼 자르면 뒤쪽 개념이 통째로 사라진다. 조판이 없는 문서에서는
    덩어리 나누기가 무력해져 조각 전체가 원문으로 오기 때문에 이게 심각해진다.

    실측(표·헤딩을 지워 대학 강의자료를 흉내 낸 판):
        절이 자기 개념을 하나도 못 받음   필기 22% · 실기 29%
        개념 기준 유실                    필기 42% · 실기 48%
    조판이 있는 실기 원본에서는 1%라 안 보이던 문제다. **확정 타깃이 강의자료이므로
    조판 있는 문서에서만 되는 것은 된 게 아니다** — ⓪에 걸었던 기준을 여기도 건다.

    줄 단위로 본다. 먼저 개념마다 자기 줄을 하나씩 확보하고(그래야 "하나도 못
    받는 절"이 없다), 예산이 남으면 주변으로 넓힌다. 건너뛴 자리에는 `…`를 넣어
    이어붙인 글이라는 걸 모델이 알게 한다.
    """
    if len(source) <= budget:
        return source
    lines = source.splitlines()
    squashed = [_sq(ln) for ln in lines]

    # 1차 — 개념마다 처음 등장하는 줄 하나씩.
    anchors: set[int] = set()
    for c in concepts:
        forms = [_sq(a) for a in aliases(c.key)]
        for i, body in enumerate(squashed):
            if any(f and f in body for f in forms):
                anchors.add(i)
                break
    if not anchors:
        return source[:budget]

    # 2차 — 예산이 남는 만큼 앵커 주변으로 넓힌다.
    keep = set(anchors)
    used = sum(len(lines[i]) + 1 for i in keep)
    for radius in (1, 2, 3):
        for i in sorted(anchors):
            for j in (i - radius, i + radius):
                if not (0 <= j < len(lines)) or j in keep:
                    continue
                cost = len(lines[j]) + 1
                if used + cost > budget:
                    continue
                keep.add(j)
                used += cost

    out: list[str] = []
    prev = -2
    for i in sorted(keep):
        if out and i != prev + 1:
            out.append("…")
        out.append(lines[i])
        prev = i
    return "\n".join(out)


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
        clipped = clip_around(source_text.strip(), concepts)
        source_part = (
            f"\n<교재 원문 (참고)>\n{clipped}\n</교재 원문>\n"
            "※ 원문은 PDF 추출본이라 공백·줄바꿈이 뒤틀려 있고 항목 번호나 잡음이\n"
            "  섞여 있을 수 있다. 읽어서 이해하되 잡음은 버려라.\n"
        )

    profile_part = f"\n{profile_block}\n" if profile_block else "\n"

    return f"""너는 학습 콘텐츠를 쓰는 에이전트다. 아래 개념들을 한 화면 분량으로 설명하라.

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
4. **빈칸 {len(concepts)}개 — 개념마다 하나씩.** 빠뜨리면 그 개념을 아는지
   판단할 수 없다. 문장 하나에 빈칸은 하나만. concept에 어느 개념인지 적어라.

   ⚠️ **`kind`를 반드시 넣고, 빈칸들이 전부 같은 kind면 안 된다.**
   전부 같은 모양이면 개념을 아는 게 아니라 **정의문을 외우게** 된다.

   "정의"  위에 준 정의를 **풀어서** 읽어주고 이름을 묻는다.
           ⚠️ 정의를 **그대로 옮겨 적지 마라.** 같은 뜻을 다른 말로 써라
   "상황"  정의 대신 **그 개념이 실제로 벌어지는 장면**을 한 문장으로 묘사하고
           이름을 묻는다. 교재의 예시·적용 대목이 있으면 그걸 쓴다
   "성질"  **개념명을 문장 안에 두고** 그 개념의 성질·수치·순서를 비운다.
           답은 개념명이 아니라 원문에 있는 말이다. 지어내지 마라

   {len(concepts)}개 중 "정의"는 절반을 넘기지 마라.

   그리고 **조사나 서술어를 비우지 마라** — 문법으로 풀려 인출이 안 된다.
   (X) …는 이전 단계로 ____ 수 없다   → '돌아갈'은 문맥으로 나온다
5. **객관식 1개 — 개념들을 구별하는 문항.** 빈칸이 "이걸 아는가"라면 객관식은
   "이것들을 가를 수 있는가"다. **위 개념 중 여럿을 보기로 넣어** 헷갈리는
   지점을 묻어라. 한 개념만 묻는 문항은 빈칸과 중복이니 만들지 마라.
6. 학습자가 읽을 글이다. "정의에 따르면" 같은 메타 표현은 쓰지 마라.
{profile_part}
아래 JSON 객체 하나만 출력한다(설명·코드펜스 금지):
{_schema_for(concepts)}

괄호 안 `(…)`는 네가 실제 문장으로 채워라. answer와 concept는 위 개념 그대로 써라.
concept 필드에는 {keys} 중 하나를 정확히 써라."""


def _clean_optional(value: object) -> str:
    """모델이 null을 문자열 "null"로 보내는 사고를 흡수한다(실측)."""
    if not isinstance(value, str):
        return ""
    text = value.strip()
    return "" if text.lower() in {"null", "none", "n/a", ""} else text


def _grounded(answer: str, concepts: list[ConceptBrief], source: str) -> bool:
    """정답이 **이 절과 실제로 관련 있는가.**

    스키마 예시를 구체적인 문항으로 바꿨더니 모델이 그걸 그대로 베끼기 시작했다.
    실측 사고: `접근 통제 기술` 절(DAC·MAC·RBAC)에 이런 빈칸이 나왔다 —
        "이전 단계로 돌아갈 수 없는 고전적 생명주기 모형을 ____ 이라 한다." (답: 폭포수 모형)
    placeholder를 베낄 때보다 나쁘다. 멀쩡해 보여서 형식 검사를 통과한다.

    문구를 막는 대신 **근거를 요구한다** — 정답은 이 절의 개념이거나 원문에 있는
    말이어야 한다. 원문이 없으면(⓪ 밖의 절) 검사를 건너뛴다. 근거가 없다고
    멀쩡한 문항까지 버리면 손해가 더 크다.
    """
    ans = _sq(answer)
    if not ans:
        return False
    for c in concepts:
        if any(_sq(a) and (_sq(a) in ans or ans in _sq(a)) for a in aliases(c.key)):
            return True
    return not source or ans in _sq(source)


def accepted_answers(
    answer: str, concepts: list[ConceptBrief], source: str = ""
) -> list[str]:
    """채점에서 **정답으로 인정할 표기들.**

    실측 사고: `폭포수`라고 적었는데 정답이 `폭포수 모형`이라 오답 처리됐다.
    개념을 정확히 꺼냈는데 분류어를 안 붙였다고 틀렸다고 하면 **인출이 아니라
    표기를 측정하는 것**이다.

    넓히는 방향 넷:
      · 괄호 병기를 뗀/만 남긴 형태   `강제 접근 통제 (MAC)` → `MAC`
      · 교재의 분류어를 뗀 형태        `폭포수 모형` → `폭포수`
      · **원문이 단 약어**             `익스트림 프로그래밍` → `XP`
        (개념명엔 없고 교재 헤딩에만 있다. 개념의 21~26%가 여기서 별칭을 얻는다)
      · 위 셋의 조합

    다만 무한정 넓히지 않는다. **이 절의 다른 개념과 겹치는 형태는 뺀다** —
    `자료 결합도`를 `자료`로 인정했는데 절에 `자료 사전`이 있으면 둘을 못 가린다.
    두 글자 미만도 뺀다.

    분류어 문턱을 묶기(3)보다 낮은 **2**로 둔다. `하향식 설계`/`상향식 설계`는
    둘뿐이라 3이면 안 걸리는데, 채점에서 `하향식`을 틀렸다고 하면 안 된다.
    채점의 오탐은 관대함이고 묶기의 오탐은 절이 잘못 만들어지는 것이라 비용이 다르다.
    """
    cats = category_words([c.key for c in concepts], min_share=2)
    forms: list[str] = []
    for alias in aliases(answer):
        forms.append(alias)
        parts = alias.split()
        if len(parts) >= 2 and parts[-1] in cats:
            forms.append(" ".join(parts[:-1]))
    # 개념 정의와 원문에서 교재가 단 약어를 찾는다.
    haystack = "\n".join([c.definition for c in concepts] + [source])
    if haystack.strip():
        forms += source_aliases(answer, haystack)

    # 다른 개념과 헷갈리는 형태는 제외한다.
    others = [c.key for c in concepts if _sq(c.key) != _sq(answer)]
    out: list[str] = []
    for f in dict.fromkeys(forms):
        s = _sq(f)
        if len(s) < 2:
            continue
        if any(s == _sq(o) or s in _sq(o) for o in others):
            continue
        out.append(f)
    return out or [answer]


def _answer_concept(answer: str, concepts: list[ConceptBrief]) -> str | None:
    """정답이 가리키는 개념. 못 찾으면 None.

    객관식은 여러 개념을 구별하는 문항이라 `concept_keys`가 절 전체다. 그래서
    화면이 오답을 기록할 때 **첫 개념에 몰아주는 사고**가 있었다 — 실측에서
    객관식 5/5가 오귀속이었고, 그게 `wrong_by_concept → weak_concepts →
    carry_over → 다음 목차 설명`으로 흘러 **학습 루프의 입력을 오염**시켰다.

    "이 문항이 실제로 묻는 개념"을 따로 실어 보낸다. 못 찾으면 **None을 준다** —
    아무 개념에나 붙이느니 절 단위로만 세는 게 낫다. 틀린 통계는 없는 통계보다 나쁘다.
    """
    ans = _sq(answer)
    if not ans:
        return None
    for c in concepts:  # 정확히 같은 표기 우선
        if any(_sq(a) == ans for a in aliases(c.key)):
            return c.key
    for c in concepts:  # 표기가 조금 달라도 서로 포함하면 같은 것으로 본다
        if any(_sq(a) and (_sq(a) in ans or ans in _sq(a)) for a in aliases(c.key)):
            return c.key
    return None


def parse_response(
    raw: str, concepts: list[ConceptBrief], source: str = ""
) -> list[Block]:
    """LLM 응답 → 블록 목록. 깨진 항목은 버리고 나머지는 살린다.

    부가 항목(비유·빈칸) 하나가 깨졌다고 설명 본문까지 잃으면 손해가 크다.
    `source`를 주면 정답이 이 절과 관련 있는지까지 본다(`_grounded`).
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

    # 최근 틀린 개념을 지금 배우는 것과 엮어 짚는 문단. **본문과 따로 받는다** —
    # 비유를 분리한 것과 같은 이유다. 이건 학습자 이력에서 온 정보라 "원문 사실만
    # 써라"와 프롬프트 안에서 충돌하고, 본문 안에 섞으라고 하면 모델이 안전한 쪽
    # (그냥 안 씀)을 택한다. 실측: 본문 안 지시로는 관련 있는 절에서도 0회.
    tie_in = _clean_optional(data.get("tie_in"))
    if tie_in:
        blocks.append(
            Block("tie_in", {"text": tie_in, "label": "여기서 잠깐"}, concept_keys=all_keys)
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
        # 이 절과 무관한 정답이면 다른 절 문항이거나 스키마 예시를 베낀 것이다.
        if not _grounded(answer, concepts, source):
            continue
        concept = item.get("concept")
        concept = concept if concept in valid_keys else None
        blocks.append(
            Block(
                "cloze",
                {
                    "sentence": sentence,
                    "answer": answer,
                    # 문항 유형(정의/상황/성질). 화면에는 안 쓰고 **다양성 측정용**이다.
                    # 유형 라벨로 학습자를 가두지 않는다는 원칙은 그대로다.
                    "kind": _clean_optional(item.get("kind")) or "정의",
                    # 채점에서 정답으로 인정할 표기들. 화면이 이걸로 맞춘다 —
                    # `폭포수`라고 적었는데 `폭포수 모형`이라 틀렸다고 하면
                    # 인출이 아니라 표기를 측정하는 것이다.
                    "accept": accepted_answers(answer, concepts, source),
                },
                concept_keys=(concept,) if concept else all_keys,
            )
        )

    # 인출은 화면당 객관식 하나(dict)라 그 모양으로 시작했는데, 형성평가는 단원당
    # 여러 개(list)다. 둘 다 받는다 — dict 하나면 원소 하나짜리 목록과 같다.
    raw_mcq = data.get("mcq")
    mcqs = [raw_mcq] if isinstance(raw_mcq, dict) else raw_mcq or []
    for mcq in mcqs:
        if not isinstance(mcq, dict):
            continue
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
            and _grounded(answer, concepts, source)
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
                        # 이 문항이 실제로 묻는 개념. 오답을 여기에 기록한다.
                        # None이면 화면이 절 단위로만 기록한다.
                        "concept": _answer_concept(answer, concepts),
                    },
                    # 보기 전체가 이 절 개념들이라 concept_keys는 절 전체가 맞다.
                    # 다만 **채점 귀속에는 쓰면 안 된다** — 위 content.concept를 쓸 것.
                    concept_keys=all_keys,
                )
            )

    return blocks


def retrieval_gap(blocks: list[Block], concepts: list[ConceptBrief]) -> list[str]:
    """이름 인출이 한 번도 없는 개념 — **인출 누락**.

    설명에 언급되기만 하고 꺼내보지 않은 개념은 "안다/모른다"를 판정할 수
    없다. 커리큘럼을 개인화할 데이터가 그만큼 비는 것이므로 커버리지와 별개로
    따로 센다.

    ⚠️ 라벨만 보고 세면 안 된다. 성질 유형은 답이 개념명이 아닌데
    `concept` 라벨로 세면 미측정이 오측정으로 바뀐다(`retrieval_label`).
    """
    from .retrieval_label import recall_asked

    asked = recall_asked(blocks, concepts)
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


def _mentions_one(text: str, key: str) -> bool:
    if key.replace(" ", "") in text.replace(" ", ""):
        return True
    tokens = [t for t in key.split() if len(t) >= 2]
    # 남은 토큰이 하나뿐이면 부분 매칭이 위험하다. `제 1 정규형`에서 `제`와 `1`이
    # 걸러지면 `정규형` 하나만 남아, 본문의 제2·제3정규형까지 언급으로 쳐진다.
    # 통짜 일치(위)에서 이미 실패했으므로 여기서는 아닌 것으로 본다.
    # 실측: 이 함정에 걸리는 개념이 필기 5개·실기 18개.
    if len(tokens) < 2:
        return False
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
