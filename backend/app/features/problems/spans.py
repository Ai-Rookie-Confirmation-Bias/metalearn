"""[순수로직] 원문을 출제 단위(span)로 쪼갠다.

DB·LLM 비의존. 생성의 **입력 단위**를 바꾸는 모듈이다.

왜 필요한가(볼륨 실측):
    per_level=2   수율 83%  커버리지 39%  177초
    per_level=5   수율 60%  커버리지 33%  303초
    per_level=10  수율 47%  커버리지 59%  338초  ← 30문항 요구에 12문항 폐기
한 호출에 많이 요구할수록 수율이 무너지고, 커버리지는 문항 수를 3배로 늘려도
따라오지 않았다(LLM이 눈에 띄는 표 하나를 더 파고들 뿐이다). 게다가 원문·프롬프트가
커지면서 매 실행마다 120초 타임아웃이 한 번씩 걸렸다.

세 증상의 원인이 같다 — **한 번에 너무 큰 것을 요구한다.** 그래서 원문을 작은
구간으로 쪼개고 구간마다 소량을 생성한다:
  · 커버리지가 희망이 아니라 **전 span 순회로 구조적 보장**된다
  · 요구가 작아 실패할 여지가 줄고, 호출이 짧아 타임아웃을 피한다
  · 문항 수를 숫자로 지정하는 대신 **원문 크기에서 자연히 나온다**
  · 레벨도 구조가 된다 — span 하나면 L1/L2, 서로 다른 span 둘이면 L3
"""
import re
from dataclasses import dataclass

from app.features.problems.coverage import _HEADING_RE
from app.features.problems.grounding import normalize

# 이보다 짧은 구간은 다음 줄과 합친다 — 한 문항을 만들 재료가 못 된다.
MIN_SPAN_CHARS = 40
# 이보다 길면 한 호출에 담기 부담스럽다(볼륨 실측에서 확인된 실패 원인).
MAX_SPAN_CHARS = 400
# 표 구분행(`| --- |`)은 내용이 아니다.
_TABLE_RULE_RE = re.compile(r"^[\s|:-]+$")


@dataclass(frozen=True)
class Span:
    """출제 근거가 될 원문 구간 하나."""

    index: int
    heading: str  # 소속 소제목 — 맥락으로만 보여주고 근거로 인용하지 않는다
    text: str  # 원문 표기 그대로 (근거 대조 대상이므로 가공하지 않는다)

    @property
    def length(self) -> int:
        return len(normalize(self.text))


def _closes_unit(line: str) -> bool:
    """이 줄에서 끊어도 의미 단위가 쪼개지지 않는가.

    파싱된 표는 한 논리 행이 여러 물리 줄에 걸친다(셀 안 줄바꿈이 빈 줄로 남는다).
    길이만 보고 끊으면 용어와 설명이 갈라져 — "**최적 적합**"과 "단편화를 최소화"가
    다른 구간으로 떨어져 — 어느 쪽으로도 문항을 만들 수 없게 된다.
    표 행은 `|`로 끝나므로, 행 중간(`|`는 있는데 끝이 아님)에서는 끊지 않는다.
    """
    stripped = line.rstrip()
    if stripped.endswith("|"):
        return True  # 표 행이 닫혔다
    return "|" not in stripped  # 산문 줄은 아무 데서나 끊어도 된다


def split(source: str) -> list[Span]:
    """원문을 span 목록으로 쪼갠다.

    제목은 span 자체가 되지 않고 뒤따르는 구간의 heading으로 붙는다(이름표는
    출제 근거가 못 되지만 맥락으로는 필요하다). 짧은 줄은 다음 줄과 합쳐
    MIN_SPAN_CHARS를 넘기고 **의미 단위가 닫히는 지점**에서 확정한다.
    """
    spans: list[Span] = []
    heading = ""
    buffer: list[str] = []

    def flush() -> None:
        nonlocal buffer
        if not buffer:
            return
        text = "\n".join(buffer).strip()
        if len(normalize(text)) >= MIN_SPAN_CHARS // 2:  # 마지막 조각은 관대하게
            spans.append(Span(index=len(spans), heading=heading, text=text))
        buffer = []

    for raw in source.splitlines():
        if _TABLE_RULE_RE.match(raw) or not raw.strip():
            continue
        if _HEADING_RE.match(raw):
            flush()  # 제목을 만나면 이전 구간을 닫는다
            heading = normalize(raw)
            continue
        buffer.append(raw)
        size = len(normalize("\n".join(buffer)))
        # MAX는 무조건 끊는다 — 표가 깨져 행 끝이 영영 안 오는 원문에서
        # 구간 하나가 무한정 커지면 span 분할의 의미가 사라진다.
        if size >= MAX_SPAN_CHARS or (size >= MIN_SPAN_CHARS and _closes_unit(raw)):
            flush()
    flush()
    return spans


def pair_indices(items: list[Span], limit: int) -> list[tuple[int, int]]:
    """비교·종합(L3)용 span 쌍을 고른다.

    모든 조합을 쓰면 span 16개에 120쌍이 되어 호출이 폭증한다. **같은 제목 아래
    인접한** 쌍만 고른다 — 원문에서 나란히 놓인 같은 표의 항목이 비교 대상이기
    때문이다(최적 적합 ↔ 최악 적합, FIFO ↔ LRU). 제목이 다른 구간끼리 묶으면
    (기억장치 배치 전략 ↔ 페이지 교체 알고리즘) 비교할 축이 없어 모델이 빈
    배열을 돌려준다 — 실측에서 L3 수확이 0이었던 원인이다.
    """
    if len(items) < 2 or limit <= 0:
        return []
    pairs = [
        (a.index, b.index)
        for a, b in zip(items, items[1:])
        if a.heading == b.heading
    ]
    if not pairs:  # 제목이 없거나 전부 다른 원문 — 인접 쌍으로 폴백
        pairs = [(a.index, b.index) for a, b in zip(items, items[1:])]
    if len(pairs) <= limit:
        return pairs
    # 고르게 뽑아 원문 전체에 흩어지게 한다(앞부분에만 몰리지 않도록).
    step = len(pairs) / limit
    return [pairs[int(i * step)] for i in range(limit)]
