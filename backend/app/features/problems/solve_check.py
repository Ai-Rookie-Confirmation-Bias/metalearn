"""[게이트4] 문항 풀이 검증 — Generate-then-Validate.

검수 LLM이 **학습자의 상황을 재현**한다: 출제 정답을 숨긴 채 원문과 보기만
보고 직접 문제를 푼다. 그 답을 코드가 출제 정답과 대조한다.
  · 검수가 다른 답을 고르면 → 학습자도 못 푸는 문항이다
  · 검수가 "다른 보기도 정답"이라고 하면 → 정답 비유일(복수정답) 결함이다

왜 필요한가(실측): 아래 문항은 기계 게이트 3개(Pydantic·서술형·근거대조)를
전부 통과했지만 **보기 4개가 모두 정답**이었다.
    Q. 교체 전략의 예시로 제시된 것은?  ▶FIFO / OPT / LRU / LFU
    근거: "ex. FIFO, OPT, LRU, LFU, NUR ···"   ← 원문에 넷 다 예시로 나열됨
"보기가 실제로 오답인가"는 의미 판정이라 문자열 대조로는 잡히지 않는다.

설계는 feat/yoonhs-integration의 `verify_cloze_drafts`(cloze 풀이 검증)에서
가져왔다. 그쪽이 겨냥한 IWF(Item-Writing Flaws) 5종 중 '정답 비유일'이
mcq에서도 같은 형태로 재현되므로, 같은 철학을 mcq로 확장한다.

정책 — **관대 통과(net-additive)**: 검수 호출·파싱이 실패하면 전원 통과시킨다.
검증이 죽었다고 생성 결과 전체를 버리지는 않는다(integration faithfulness와 동일).
"""
import json
import logging
import re

from app.core.llm.base import LLMClient
from app.features.problems.schemas import Problem, ProblemType

logger = logging.getLogger(__name__)

# 검수 답과 출제 정답 비교는 채점보다 관대하게 — 표기 차이로 멀쩡한 문항을
# 버리지 않기 위해 공백·문장부호를 걷어내고 포함 관계까지 인정한다.
_TIGHT_RE = re.compile(r"[\s.,·'\"()\[\]]+")


def _tight(s: str) -> str:
    return _TIGHT_RE.sub("", s)


def answers_match(expected: str, got: str) -> bool:
    """출제 정답 vs 검수 답(항목 하나) — 정규화 후 동등하거나 포함 관계면 일치."""
    e, g = _tight(expected), _tight(got)
    return bool(e) and bool(g) and (e == g or e in g or g in e)


def as_list(value: object) -> list[str]:
    """검수 응답을 항상 목록으로 — 유형에 따라 문자열/배열이 섞여 온다."""
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    text = str(value or "").strip()
    return [text] if text else []


def answers_equivalent(kind: ProblemType, expected: list[str], got: list[str]) -> bool:
    """유형별로 출제 정답과 검수 답이 같은지 판정한다.

    order는 **순서까지**, multi는 **구성(집합)만**, mcq·ox는 항목 하나를 본다.
    """
    if not expected or not got:
        return False
    if kind is ProblemType.ORDER:
        return len(expected) == len(got) and all(
            answers_match(e, g) for e, g in zip(expected, got)
        )
    if kind is ProblemType.MULTI:
        if len(expected) != len(got):
            return False
        remaining = list(got)
        for e in expected:
            hit = next((g for g in remaining if answers_match(e, g)), None)
            if hit is None:
                return False
            remaining.remove(hit)
        return True
    return answers_match(expected[0], got[0])


# 유형별로 검수자에게 요구할 답의 형태가 다르다.
_ASK = {
    ProblemType.MCQ: "정답 보기의 텍스트 하나",
    ProblemType.MULTI: "정답인 보기 텍스트를 **모두** 담은 배열",
    ProblemType.OX: '"O" 또는 "X"',
    ProblemType.ORDER: "보기 전체를 올바른 순서로 배열한 배열",
}


def build_prompt(problems: list[Problem], source_text: str) -> str:
    """정답을 **숨기고** 문제만 제시한다 — 검수가 진짜로 풀어야 의미가 있다."""
    blocks = []
    for i, p in enumerate(problems):
        head = f"[문항 {i}] ({p.type}) {p.question}"
        if p.options:
            head += "\n" + "\n".join(f"   - {o}" for o in p.options)
        head += f"\n   → 답 형식: {_ASK[p.type]}"
        blocks.append(head)
    joined = "\n\n".join(blocks)
    return f"""너는 학습 문항 검수자다. 아래 [원문]만 읽은 학습자가 각 문제를 푼다고 하자.

각 문항에 대해:
1) answer — 네가 고른 답. **문항마다 표시된 '답 형식'을 그대로 따르라**
   (하나면 문자열, 여럿이면 배열).
2) also_correct — 원문에 비추어 **정답으로 인정될 수 있는 다른 답**을 적극적으로 찾아
   나열하라. 좋은 문항은 정답이 유일하다 — 하나라도 있으면 그 문항은 결함이다.
   (예: 원문이 "ex. FIFO, OPT, LRU, LFU"처럼 나열했는데 보기가 그 목록에서 나왔다면
    보기 전부가 정답이므로 모두 여기에 적어라. 순서 배열 문항이라면 원문 근거로는
    다르게 배열해도 말이 되는 순서를 여기에 적어라.)
3) unanswerable — 원문만으로는 정답을 특정할 수 없으면 true.

[원문]
{source_text[:4000]}

[문항들]
{joined}

출력은 아래 JSON 객체 하나만(설명·코드펜스 금지):
{{"items": [{{"id": 0, "answer": "고른 답(형식에 맞춰)", "also_correct": [], "unanswerable": false}}]}}"""


async def verify_problems(
    llm: LLMClient, problems: list[Problem], source_text: str
) -> tuple[list[Problem], list[str]]:
    """검수 풀이로 결함 문항을 걸러낸다. 반환 (통과 문항, 폐기 사유 목록).

    배치 1콜로 처리한다(문항 수만큼 호출하면 비용이 선형으로 늘어난다).
    """
    if not problems:
        return [], []

    try:
        raw = await llm.generate(
            build_prompt(problems, source_text),
            response_format={"type": "json_object"},
            temperature=0.0,  # 검수는 재현성이 중요하므로 창의성 최소
        )
        payload = json.loads(raw[raw.find("{") : raw.rfind("}") + 1])
        rows = {
            int(r["id"]): r
            for r in payload.get("items") or []
            if isinstance(r, dict) and isinstance(r.get("id"), int)
        }
    except Exception:  # noqa: BLE001 — 검수 실패는 관대 통과(net-additive)
        logger.warning("문항 풀이검증 호출 실패 — 전원 통과 폴백")
        return problems, []

    passed: list[Problem] = []
    reasons: list[str] = []
    for i, p in enumerate(problems):
        row = rows.get(i)
        if row is None:
            passed.append(p)  # 검수가 빠뜨린 문항은 관대 통과
            continue

        if row.get("unanswerable"):
            reasons.append("원문만으로 정답을 특정할 수 없음")
            continue

        expected = p.answer_texts
        alts = row.get("also_correct") or []

        if p.type is ProblemType.ORDER:
            # 순서 문항은 "다른 순서도 성립"이 곧 정답 비유일이다.
            if alts:
                reasons.append("정답 비유일 — 다른 순서로도 성립")
                continue
        else:
            # 출제 정답에 없는 답이 '정답 가능'으로 지목되면 정답 비유일.
            others = [
                str(o)
                for o in alts
                if str(o).strip()
                and not any(answers_match(e, str(o)) for e in expected)
            ]
            if others:
                reasons.append(f"정답 비유일 — 다른 보기도 정답 가능({len(others)}개)")
                continue

        got = as_list(row.get("answer"))
        # 검수가 also_correct를 비워둔 채 answer에 여러 보기를 한꺼번에 적는
        # 형태로 "다 정답"을 표현하는 경우가 있다(실측: "FIFO, OPT, LRU, LFU").
        # answers_match는 약어↔풀네임을 살리려고 포함 관계를 인정하므로, 이런
        # 나열형 답을 그대로 대조하면 출제 정답과 일치한다고 오판한다.
        # 정답이 원래 하나인 유형에서만 의미가 있다.
        if (
            p.type is ProblemType.MCQ
            and got
            and len([o for o in p.options if answers_match(o, got[0])]) >= 2
        ):
            reasons.append("검수 답이 여러 보기를 동시에 지목 — 정답 비유일")
            continue
        if got and not answers_equivalent(p.type, expected, got):
            reasons.append("검수자가 출제 정답과 다른 답을 냄")
            continue

        passed.append(p)
    return passed, reasons
