"""[순수로직] 인출 문항이 **실제로 요구하는 수준**을 판정한다.

DB·LLM 비의존. 인출 에이전트가 **자기 출력을 스스로 재는 도구**다.
프롬프트에 유형을 시키는 것과 별개다 — 모델이 붙인 라벨은 자기 신고라 못 믿는다.
실측에서 `kind="상황"`이라고 답한 문항이 정의문을 그대로 옮긴 것이었다.

## `feat/problems`의 levels.py에서 가져온 것

원리와 규율을 가져왔다.
  · 라벨을 모델에게 맡기지 말고 **기계로 판정**한다
  · **강등이지 폐기가 아니다** — 수준이 낮을 뿐 문항 자체는 멀쩡하므로 버리면
    문항 수만 줄고 재시도를 태운다
  · 근거가 원문의 **여러 곳**을 필요로 하면 종합·구별이다(citation_spans)
  · 정답이 여럿인 유형은 범주 판단이 필요하므로 재인이 아니다

## 그대로 못 가져온 것

problems는 "정답이 근거 문구에 그대로 있으면 재인"으로 봤다. 우리는 못 쓴다 —
빈칸은 정답이 문장에서 빠져 있고(`parse_response`가 검사), 근거가 되는 설명
본문에는 정답이 **항상** 있다(`coverage`가 그걸 요구한다). 쓰면 전부 재인이 된다.

우리 맥락의 등가물은 **"문항이 개념 정의문을 그대로 옮겼는가"**다. 정의를 복사해
이름만 비우면 학습자는 개념이 아니라 **정의문을 기억했는지**만 확인받는다.

    L1 재인   빈칸 문장이 개념 정의문과 크게 겹친다
    L2 적용   정의를 다른 말로 바꿨거나 상황으로 만들었다
    L3 구별   여러 개념을 대조해야 답한다(객관식 보기가 절 개념 여럿)
"""
from __future__ import annotations

import re

from .excerpt import normalize_spaces

L1_RECALL = 1  # 재인 — 정의문을 되읽는다
L2_APPLY = 2  # 적용 — 다른 말로 바꿔 묻는다
L3_DISCRIMINATE = 3  # 구별 — 개념 사이를 가른다

# 이 비율 이상 겹치면 정의문을 옮겨 적은 것으로 본다.
# 실측으로 정한다 — 문항 분포를 보고 조정한다(bench/level_check.py).
COPY_RATIO = 0.6
# 객관식이 구별 문항이 되려면 보기에 이 절 개념이 몇 개 있어야 하는가.
MIN_DISTINCT = 2


def _grams(text: str, n: int = 2) -> set[str]:
    t = re.sub(r"[^\w가-힣]", "", normalize_spaces(text))
    return {t[i : i + n] for i in range(len(t) - n + 1)}


def overlap(a: str, b: str) -> float:
    """a가 b에 얼마나 담겨 있는지(0~1). a 기준이라 길이 차이에 덜 흔들린다."""
    x, y = _grams(a), _grams(b)
    return len(x & y) / len(x) if x else 0.0


def assess_cloze(sentence: str, definition: str, source: str = "") -> int:
    """빈칸 하나의 수준.

    빈칸을 뺀 나머지(= 학습자가 읽는 단서)를 개념 정의문과 견준다. 정의를 그대로
    옮겼으면 재인이다. **정답이 무엇인지는 보지 않는다** — 정의문을 베꼈는지가
    문제지 답이 뭔지가 문제가 아니다.
    """
    stem = sentence.replace("____", " ").strip()
    if not stem or not definition.strip():
        return L2_APPLY  # 잴 수 없으면 낮게 잡지 않는다(강등은 근거가 있을 때만)
    if overlap(definition, stem) >= COPY_RATIO:
        return L1_RECALL
    # 원문의 여러 곳을 엮어야 하면 단순 적용을 넘는다.
    if source and _spread(stem, source) >= 2:
        return L3_DISCRIMINATE
    return L2_APPLY


def assess_mcq(options: list[str], concept_keys: list[str]) -> int:
    """객관식 하나의 수준.

    보기에 이 절 개념이 여럿이면 **개념 사이를 가르는** 문항이다. 하나뿐이면
    나머지는 절 밖에서 온 들러리라 빈칸과 다를 게 없다.
    """
    keys = {re.sub(r"\s+", "", k) for k in concept_keys}
    hit = sum(1 for o in options if re.sub(r"\s+", "", o) in keys)
    return L3_DISCRIMINATE if hit >= MIN_DISTINCT else L2_APPLY


def _spread(stem: str, source: str) -> int:
    """단서가 원문의 서로 다른 몇 줄에 걸쳐 있는지.

    `problems`의 `citation_spans`와 같은 발상이다 — 비교·종합은 본질적으로
    여러 곳을 필요로 한다. 우리는 근거를 따로 안 받으므로 줄 단위로 센다.
    """
    lines = [ln for ln in normalize_spaces(source).splitlines() if len(ln.strip()) > 10]
    return sum(1 for ln in lines if overlap(ln, stem) >= 0.4)


def mix(levels: list[int]) -> dict[str, int]:
    """절 하나의 수준 분포. 화면에 안 쓰고 **품질 지표로만** 쓴다."""
    return {
        "L1": levels.count(L1_RECALL),
        "L2": levels.count(L2_APPLY),
        "L3": levels.count(L3_DISCRIMINATE),
    }
