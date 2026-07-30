"""[순수로직] 인지 수준(레벨) 판정 — 문항이 실제로 요구하는 난이도.

DB·LLM 비의존. 게이트 ①~④가 "결함이 없는가"를 보고 ⑤가 "빠짐없이 다뤘는가"를
본다면, 여기는 **"난이도 라벨이 맞는가"**를 본다.

왜 필요한가(실측): 아래 문항은 모든 게이트를 통과했지만 L3로 태깅돼 있었다.
    Q(L3). 최악 적합(Worst Fit)이 목표로 하는 것은?  ▶단편화를 최대화
    근거:  "단편화를 '최대화'하는 분할 영역에 데이터 배치"
근거 한 줄을 그대로 되묻는 단순 재인이므로 L1이다. 이런 오분류가 쌓이면
레벨 게이트("L1 80% 통과해야 L2 언락")가 무의미해진다 — 레벨 사이에 실제
난이도 차이가 없으면 진도 시스템 전체가 껍데기가 된다.

판정 신호 2개(둘 다 기계적으로 구할 수 있다):
  ① 정답이 근거 문구에 그대로 들어있는가
     → 근거를 읽으면 답이 바로 보인다 = 단순 재인(L1)
  ② 근거가 원문의 서로 다른 몇 곳을 인용했는가 (grounding.citation_spans)
     → 비교·종합(L3)은 본질적으로 여러 곳을 필요로 한다

**강등이지 폐기가 아니다.** 레벨이 틀렸을 뿐 문항 자체는 멀쩡하므로(근거 실재,
정답 유일) 버리면 문항 수만 줄고 재시도를 태운다. 라벨을 낮춰 살린 뒤, 부족한
레벨은 재시도 피드백으로 다시 요청한다.
"""
import re

from app.features.problems.grounding import citation_spans, normalize

_TIGHT_RE = re.compile(r"[\s.,·'\"()\[\]]+")


def _tight(s: str) -> str:
    return _TIGHT_RE.sub("", normalize(s))


def answer_visible_in_evidence(answer: str, evidence: str) -> bool:
    """정답 보기가 근거 문구에 그대로 담겨 있으면 True(= 재인 수준).

    예) 근거 "단편화를 '최대화'하는 분할 영역에 데이터 배치"
        정답 "단편화를 최대화"  → True (근거를 읽으면 답이 보인다)
    반례) 근거 "단편화를 '최소화'하는 분할 영역에 데이터 배치"
        정답 "Best Fit"       → False (용어↔설명 매핑이 필요하다)
    """
    a, e = _tight(answer), _tight(evidence)
    return bool(a) and bool(e) and a in e


def assess(answer: str, evidence: str, source: str) -> int:
    """이 문항이 실제로 요구하는 레벨(1~3)을 추정한다.

    보수적으로 판정한다 — 애매하면 낮은 쪽이 아니라 **요청한 레벨을 유지**할 수
    있도록, 여기서는 '확실히 쉬운 경우'만 낮게 잡는다. 강등은 service가
    요청 레벨과 비교해 결정한다.
    """
    if answer_visible_in_evidence(answer, evidence):
        return 1  # 근거를 읽으면 답이 보인다 — 종합도 적용도 필요 없다
    return 3 if citation_spans(evidence, source) >= 2 else 2
