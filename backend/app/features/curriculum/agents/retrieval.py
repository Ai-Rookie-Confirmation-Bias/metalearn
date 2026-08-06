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
  · 설명에 연결이 있으면 관계를 묻는 문항이 나올 수 있다(없으면 각각 묻는다)
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

## 라벨 검증 (오측정 > 미측정)

개수 게이트만으로는 부족하다. `concept` 라벨로 세면 "라벨 ≠ 실제 묻는 것"이
통과한다. `retrieval_label.scrub_blocks`가 생성·보충 직후 한 번 더 거른다.
  · 정답이 다른(화면 밖) 개념 → 폐기
  · 성질(답이 개념명 아님) → 문항은 살리고 `concept_keys`를 비워 숙련도 오귀속 차단
  · 누락 = **이름 인출**이 없는 개념 (성질만 있으면 미측정으로 남김 → 보충)

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
from ..retrieval_label import scrub_blocks
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
    """응답 스키마 — **예시를 이 화면의 개념으로 완성해서** 준다.

    ⚠️ 추상 자리(`"sentence": "…____…"`)를 주면 안 된다. 다섯 번 겪었다:
    모델이 그걸 그대로 내거나(필터에 걸려 인출 0개), 아예 빈칸 없는 평서문을
    낸다. 실측에서 `익스트림 프로그래밍` 절이 `____`가 없는 설명 문장 두 개를
    내놨다. **예시가 곧 출력**이므로 예시는 완성된 문항이어야 하고, 그러면
    베껴도 이 화면의 유효한 문항이 된다.

    ⚠️⚠️ 그 원칙을 **여기서 그대로 어겼다(여덟 번째).** 아래 두 예시 중
    "성질"만 개념으로 완성하고 "상황"은 이런 문장을 하드코딩해 뒀었다:

        "팀이 그런 방식으로 일하고 있다면 그것은 ____ 다."

    통합 검증에서 정보처리기사와 디지털 감성 디자인 — 공통점이 없는 두 교재가
    **글자 그대로 같은 이 문장**을 냈다. 실측 12화면 44빈칸 중 8개(18%),
    화면으로는 8/12. 원문 어디에도 없는 문장이다.

    방어 세 겹이 다 있는데 전부 통과한다:
      · `_TEMPLATE_MARKERS`  빈자리 표기를 잡는 것 — 이건 완성된 문장이다
      · `_DEICTIC_STARTS`    **문장 시작만** 본다. "팀이"로 시작하고
                             "그런 방식"은 중간에 있다
      · `_grounded`          answer는 이 화면의 진짜 개념이라 통과한다
    그래서 "감성 다", "자료 사전 다" 같은 게 화면에 그대로 나갔다.

    ⇒ 방어를 한 겹 더 얹는 게 아니라 **예시를 고쳤다.** 단서는 정의에서
      뽑는다(`_stem`). 모델이 이 틀을 자료에 맞게 채운 경우는 실측에서 이미
      멀쩡한 문항이었다("팀이 시스템의 구성 요소와 그들 간의 관계를 시각적으로
      표현하고 있다면 그것은 ____ 다") — 틀이 아니라 하드코딩이 문제였다.
    """
    first_c = concepts[0] if concepts else None
    first = first_c.key if first_c else "개념"
    second = concepts[1].key if len(concepts) > 1 else first
    # 상황 예시. `_stem`이 **정의**에서 단서를 뽑는다 — 개념명을 단서에 넣으면
    # 답이 문장에 노출돼 파서가 버린다. 조사는 "에 해당한다면"이라 받침을 안 탄다.
    situation = (
        f"{_stem(first_c)}에 해당한다면 그것은 ____ 이다."
        if first_c
        else "이런 성질을 가진 것에 해당한다면 그것은 ____ 이다."
    )
    options = [c.key for c in concepts[:4]] or [first]
    while len(options) < 3:
        options.append(f"{first} 아닌 것 {len(options)}")
    return f"""{{
  "cloze": [
    {{"kind": "상황", "sentence": "{situation}",
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
   "정의"  개념의 뜻을 **다른 표현으로** 풀어 묻는다 — 답은 **그 개념명**
   "상황"  그 개념이 실제로 벌어지는 **장면**을 묘사하고 이름을 묻는다 — 답은 **그 개념명**
   "성질"  개념명을 문장에 두고 그 개념의 **성질·수치·순서**를 비운다.
           답은 개념명이 아니라 설명이나 원문에 있는 말이다
   ★ **개념마다 정의 또는 상황 중 최소 하나.** 성질은 그 위에만 추가한다.
   정의/상황의 answer를 **다른 개념명**으로 쓰지 마라(이 화면 밖 개념도 금지).
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

    # ⚠️ **예시가 곧 출력이다**(일곱 번째). 예시 문장이
    # `"그런 상황에서 쓰는 것이 ____ 다."`였는데, 모델이 그걸 그대로 베껴 세 개념
    # 전부 같은 문장으로 냈다. 앞 문장을 가리키는 문장이라 파서가 다 버려 **0문항**.
    #
    # 예시는 "베껴도 무해"를 넘어 **베끼면 오히려 맞는 모양**이어야 한다.
    # 개념 정의에서 단서를 뽑아 만든다 — 베끼면 자기 개념 문장이 된다.
    # ⚠️ 정의문 뒤에 조사를 붙이면 받침에 따라 어색해진다("…표기 기호 사전**는 것은**").
    #    형성평가에서 겪고 고친 것과 같은 자리다 — **문장을 끊고 묻는 형태**로 쓴다.
    #    앞머리에 정의가 들어 있으니 이 문장 하나로 답이 정해진다(지시어 규칙 통과).
    examples = ",\n    ".join(
        f'{{"kind": "상황", "sentence": "{_stem(c)}. 이것을 가리키는 말은 ____ 이다.", '
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
   다른 개념 문항은 만들지 마라. **kind는 상황 또는 정의**, answer는 **그 개념명**.
   성질 유형은 만들지 마라 — 이름 인출이 빠진 개념만 채운다.
2. ★ **설명이나 정의를 그대로 옮겨 적지 마라.** 문장을 복사해 이름만 비우면
   학습자는 개념이 아니라 그 문장을 외웠는지만 확인받는다. 다른 말로 다시 써라.
3. **조사나 서술어를 비우지 마라** — 문법으로 풀려 인출이 안 된다.
4. ★ **문장 하나로 답이 정해져야 한다.** `그런 상황에서 쓰는 것이 ____ 다`처럼
   앞 문장을 가리키면 안 된다. 학습자는 설명을 덮고 이 문장만 본다 —
   무엇을 묻는지가 이 문장 안에 다 들어 있어야 한다.
5. 문장 하나에 빈칸은 하나. concept·answer에 어느 개념인지 정확히 적는다.

아래 JSON 객체 하나만 출력한다(설명·코드펜스 금지):
{{
  "cloze": [
    {examples}
  ]
}}"""


def _stem(c: ConceptBrief) -> str:
    """예시 문장의 앞부분 — **그 개념의 정의에서** 뽑는다.

    개념명이 답이므로 단서는 정의에서 와야 한다. 정의가 없으면 개념명을 되풀이하지
    않고 일반 문구를 쓴다(개념명을 단서에 넣으면 답이 문장에 노출돼 파서가 버린다).
    """
    d = (c.definition or "").strip().rstrip(".")
    if not d:
        return "이런 성질을 가진 것"
    # 정의를 한 구절로 줄인다. 길면 예시가 본문처럼 보여 규칙이 묻힌다.
    return d.split(",")[0][:40]


async def fill_only(
    section_title: str,
    concepts: list[ConceptBrief],
    grounds: str,
) -> list[Block]:
    """설명 없이 **문항만** 만든다 — 복습이 쓰는 문이다.

    학습 화면은 설명 → 인출 순서라 인출이 설명을 근거로 받는다. 복습은 설명을
    다시 보여주지 않으므로 근거가 원문(또는 개념 정의)이다. 설명 콜이 빠져
    화면당 한 콜로 끝난다.

    보충 프롬프트를 그대로 쓴다 — 거긴 이미 "개념마다 하나씩, 상황·정의로,
    답은 개념명"이 못 박혀 있다. 복습이 재려는 것과 같다.
    """
    return await _fill(
        section_title,
        concepts,
        tuple(c.key for c in concepts),
        grounds,
        "",
        grounds,
    )


async def recall_one(
    section_title: str,
    concept: ConceptBrief,
    explanation: str,
) -> Block | None:
    """개념 하나짜리 빈칸. **다시 설명을 펼친 자리에 붙는다.**

    읽고 끝내면 "봤다"는 느낌만 남고 실제로는 안 는다 — 인출 에이전트가 L1을
    강등시키는 이유가 그것이다. 다시 설명도 읽기라서, 읽었으면 바로 꺼내봐야
    학습이 된다.

    이 화면 개념이 아니므로 **커버리지·누락 게이트와 무관하다.** 그쪽은 이
    화면이 자기 개념을 다 물었는지를 보는 자리고, 여기는 지난 결손을 짚는
    자리다. 섞으면 둘 다 뜻이 흐려진다.

    실패하면 None — 다시 설명 본문은 그대로 살린다.
    """
    blocks = await _fill(
        section_title, [concept], (concept.key,), explanation, "", explanation
    )
    return next((b for b in blocks if b.type == "cloze"), None)


async def _fill(
    section_title: str,
    concepts: list[ConceptBrief],
    gap: tuple[str, ...],
    explanation: str,
    source_text: str,
    grounds: str,
    foreign_keys: tuple[str, ...] = (),
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
    # 빠진 개념의 **이름 인출**만 받는다. 라벨 검증 후 concept_keys가 비면(성질)
    # 또는 다른 개념이면 버린다 — 보충은 누락을 메우는 자리라 성질로는 부족하다.
    want = set(gap)
    return [
        b
        for b in scrub_blocks(
            parse_response(raw, concepts, grounds), concepts, foreign_keys=foreign_keys
        )
        if b.type == "cloze" and set(b.concept_keys) & want
    ]


def _levels_of(blocks: list[Block], concepts: list[ConceptBrief], source: str) -> list[int]:
    defs = {c.key: c.definition for c in concepts}
    keys = [c.key for c in concepts]
    out: list[int] = []
    for b in blocks:
        if b.type == "cloze":
            key = b.concept_keys[0] if len(b.concept_keys) == 1 else ""
            # 성질 문항은 라벨 검증이 `concept_keys`를 비운다(숙련도 오귀속 차단).
            # 정의문 대조는 계속 해야 하므로 남겨 둔 라벨을 쓴다 — 안 그러면
            # 정의를 통째로 베낀 성질 문항이 "잴 수 없으면 L2"로 게이트를 통과한다.
            key = key or str(b.content.get("concept") or "")
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
    foreign_keys: tuple[str, ...] = (),
) -> RetrievalResult:
    """인출 문항을 만들고 **스스로 재서** 품질은 다시 만들고 누락은 채운다.

    foreign_keys: 이 화면에 없는 문서 개념명. 정답이 여기 걸리면 폐기한다
    (다른 화면 개념을 이 화면 라벨에 붙이는 사고).
    """
    best: RetrievalResult | None = None
    feedback = ""
    grounds = "\n".join(x for x in (source_text, explanation) if x)
    # 이 화면 개념은 foreign이 아니다 — 중복되면 이름 인출로 살아야 한다.
    section_keys = {c.key for c in concepts}
    foreign = tuple(k for k in foreign_keys if k not in section_keys)

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
        # ★ 라벨 검증: 다른 개념이 정답이거나(폐기), 성질이면 숙련도 키를 비운다.
        blocks = scrub_blocks(
            [b for b in parse_response(raw, concepts, grounds) if b.type in ("cloze", "mcq")],
            concepts,
            foreign_keys=foreign,
        )
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
        return best or RetrievalResult(
            blocks=(), levels=mix([]), gap=tuple(c.key for c in concepts)
        )

    # ── 누락 보충 ──────────────────────────────────────────────────
    # 여기가 없어서 "개념마다 하나씩"이 프롬프트의 부탁으로만 남아 있었다.
    # 실측 81% → 아래 참조. 덧붙이기라 결과가 나빠질 수 없다.
    # 성질만 있고 이름 인출이 없는 개념도 gap에 들어간다(라벨 검증 후).
    for _ in range(MAX_FILL):
        if not best.gap:
            break
        added = await _fill(
            section_title,
            concepts,
            best.gap,
            explanation,
            source_text,
            grounds,
            foreign_keys=foreign,
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
