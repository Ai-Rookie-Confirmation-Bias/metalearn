"""[순수로직] 학습 성향 — 축 정의 · 신호 반영 · 생성 지시문 변환.

DB·LLM 비의존.

## 무엇을 재는가

성향은 **"어떻게 배우는가"**의 축이다. **"무엇을 배우는가"는 절대 건드리지 않는다.**
어려워하는 사람에게 내용을 덜 주면 그건 맞춤이 아니라 차별이다. 같은 개념을
같은 범위로 다루되, 설명하는 방식만 바꾼다.

## 왜 두 축인가

  표현(representation)  정의·형식  ↔  비유·예시
  깊이(depth)           결론만     ↔  왜 그런지까지

"큰 그림을 먼저 주기"는 축에서 뺐다. 선행 조직자는 성향과 무관하게 효과가
있으므로 **모두에게 기본 적용**한다. 세부부터 보고 싶어하는 사람은 취향이
아니라 이미 큰 그림을 아는 사람이고, 그건 성향이 아니라 수준의 문제다.

축은 `AXES`에 데이터로 정의되어 있어 추가·제거가 쉽다. 다만 축을 늘리면
조합이 지수로 늘고 측정 부담이 커지므로, 실제로 결과가 눈에 띄게 달라지는
축만 둔다.

## 왜 임계값 기반 결정적 변환인가

LLM에 "이 사람은 비유파니까 알아서 써줘"라고 맡기면 **반영됐는지 검증할 수
없다.** 점수 → 지시문이 규칙이어야 같은 성향에 같은 지시가 나가고, 그래야
"왜 이 설명이 이렇게 나왔는지"를 화면에 쓸 수 있다(서비스 정의의 전제).

## 왜 신뢰도가 필요한가

두 번 재고 확신하는 것보다 중립 생성이 낫다. **측정이 부족하면 아무 지시도
하지 않는다** — 잘못 잰 성향으로 세게 미는 쪽이 손해가 크기 때문이다.
그리고 유형 라벨("당신은 비유파")로 굳히지 않는다. 라벨은 측정 오차를
영구화하고, 학습하면서 조정될 여지를 없앤다.
"""
from __future__ import annotations

from dataclasses import dataclass

# ── 축 정의 ──────────────────────────────────────────────────────────
# 축을 늘리려면 여기에 추가한다. 지시문은 임계값을 넘을 때만 나간다.


@dataclass(frozen=True)
class Axis:
    key: str
    low_label: str  # score 0 쪽
    high_label: str  # score 1 쪽
    high_directive: str  # score > HIGH 일 때 프롬프트에 붙일 지시
    low_directive: str  # score < LOW 일 때


AXES: tuple[Axis, ...] = (
    Axis(
        key="representation",
        low_label="정의·형식으로",
        high_label="비유·예시로",
        high_directive=(
            "- 개념을 설명할 때 **일상 비유나 구체적 예시를 정의보다 먼저** 놓아라. "
            "추상적 정의로 시작하지 마라."
        ),
        low_directive=(
            "- **정의와 형식을 먼저** 제시하라. 비유는 넣지 마라 — "
            "이미 아는 사람에게 비유는 소음이다."
        ),
    ),
    Axis(
        key="depth",
        low_label="결론만",
        high_label="왜 그런지까지",
        high_directive=(
            "- 결론뿐 아니라 **왜 그렇게 되는지, 어디서 나왔는지**를 함께 써라. "
            "한계나 반례가 있으면 짚어라."
        ),
        low_directive=(
            "- **결론과 핵심만** 간결하게. 배경·유래·반례는 생략하라."
        ),
    ),
)

_BY_KEY = {a.key: a for a in AXES}

# 지시문 발동 임계값. 0.4~0.6 사이는 중립(아무 지시도 안 함).
HIGH = 0.6
LOW = 0.4
# 이보다 확신이 낮으면 점수와 무관하게 중립. 잘못 잰 성향으로 미는 것보다 낫다.
MIN_CONFIDENCE = 0.35
# 관찰 1회가 confidence에 기여하는 양. 2회면 0.6, 3회면 0.75 — 2회부터 발동한다.
_CONF_PER_OBSERVATION = 0.3


@dataclass(frozen=True)
class AxisScore:
    """축 하나의 상태. 유형 라벨이 아니라 연속 점수 + 확신도로 둔다."""

    score: float = 0.5  # 0.0 ~ 1.0, 기본은 중립
    confidence: float = 0.0
    n: int = 0  # 관찰 횟수

    @property
    def active(self) -> bool:
        """이 축이 실제로 생성에 영향을 주는가."""
        return self.confidence >= MIN_CONFIDENCE and not (LOW <= self.score <= HIGH)


Profile = dict[str, AxisScore]


def empty_profile() -> Profile:
    return {a.key: AxisScore() for a in AXES}


def observe(profile: Profile, axis_key: str, toward_high: bool) -> Profile:
    """관찰 하나를 반영한다 (A/B 선택 결과 등).

    지수이동평균으로 누적한다 — 최근 관찰에 더 무게를 두어, 학습이 진행되며
    성향이 드러나면 따라간다. 초기 몇 번은 크게 움직이고 점차 안정된다.
    """
    if axis_key not in _BY_KEY:
        raise KeyError(f"모르는 축: {axis_key}")
    cur = profile.get(axis_key, AxisScore())
    target = 1.0 if toward_high else 0.0
    # n이 커질수록 한 관찰의 영향이 줄어든다.
    weight = 1.0 / (cur.n + 2)
    score = cur.score + (target - cur.score) * max(weight, 0.25)
    n = cur.n + 1
    updated = dict(profile)
    updated[axis_key] = AxisScore(
        score=round(min(1.0, max(0.0, score)), 3),
        confidence=round(min(1.0, n * _CONF_PER_OBSERVATION), 3),
        n=n,
    )
    return updated


def directives(profile: Profile) -> list[str]:
    """프롬프트에 붙일 지시문 목록. 확신 없는 축은 아무것도 내지 않는다."""
    out: list[str] = []
    for axis in AXES:
        s = profile.get(axis.key, AxisScore())
        if not s.active:
            continue
        out.append(axis.high_directive if s.score > HIGH else axis.low_directive)
    return out


def prompt_block(profile: Profile) -> str:
    """생성 프롬프트에 그대로 끼울 블록. 지시가 없으면 빈 문자열."""
    lines = directives(profile)
    if not lines:
        return ""
    return "[이 학습자에게 맞춘 설명 방식]\n" + "\n".join(lines)


# 24 진단 ③에서 고른 설명 형식 → 프롬프트 지시문.
#
# ⚠️ 2축(`representation`·`depth`)으로 못 담는다. 진단은 네 가지를 **카드로
#    보여주고 고르게** 하는데, `table`은 어느 축에도 없고 `why`는 depth 축의
#    한쪽이다. 축은 관찰로 추정하는 값이고 이건 **사용자가 직접 고른 값**이라
#    성격도 다르다 — 추정보다 우선한다.
#
# ⚠️ 문구는 축 지시문과 같은 톤이어야 한다. 둘이 같은 프롬프트에 들어갈 수
#    있고, 어긋나면 모델이 어느 쪽을 따를지 모른다.
STYLE_DIRECTIVE: dict[str, str] = {
    "metaphor": (
        "- 개념을 설명할 때 **일상 비유나 구체적 예시를 정의보다 먼저** 놓아라. "
        "추상적 정의로 시작하지 마라."
    ),
    "definition": (
        "- **정의와 형식을 먼저** 제시하라. 비유는 넣지 마라 — "
        "이미 아는 사람에게 비유는 소음이다."
    ),
    "table": (
        "- 비교할 수 있는 것은 **표로 정리하라**(마크다운 표). 나란히 놓으면 "
        "차이가 보이는 개념들은 줄글로 늘어놓지 마라."
    ),
    "why": (
        "- 결론뿐 아니라 **왜 그렇게 되는지, 어디서 나왔는지**를 함께 써라. "
        "한계나 반례가 있으면 짚어라."
    ),
}


# 형식마다 **반드시 지켜야 하는 것**을 한 줄 더 못박는다.
#
# ⚠️ 위 `STYLE_DIRECTIVE`만으로는 안 지켜진다. 실측(같은 화면·2026-08-10):
#
#       압축 있음   metaphor 비유○  definition ○  table 표✗  why 이유✗
#       압축 없음   metaphor 비유✗  definition ○  table 표✗  why 이유✗
#
#    압축이 형식을 눌러서인 줄 알고 한참 팠는데 **압축을 빼도 똑같았다.**
#    분량과 싸운 게 아니라 원래 지시가 약했던 것이다. "표로 정리하라" 같은
#    서술형 요청은 모델이 흘려듣고, **출력할 JSON 키를 이름으로 부르며
#    "★ 반드시"를 붙여야** 따랐다.
#
# ⚠️ **분량 지시(`planner.mode_block`)에 넣지 마라.** 전에 거기에 "analogy를
#    채워라"를 박았더니 형식과 무관하게 걸려서 `table`·`why`에까지 엉뚱한
#    비유가 붙었다(2/4 오염). 무엇을 지킬지는 형식이 정할 일이다.
_ENFORCE: dict[str, str] = {
    "metaphor": (
        "- ★ `analogy`를 null로 두지 마라. 한두 문장이어도 좋으니 **반드시 채워라.**"
    ),
    "table": (
        "- ★ 비교되는 개념이 둘 이상이면 **본문(text) 안에 마크다운 표를 반드시 "
        "넣어라** — 머리행 `| 항목 | 설명 |` 다음 줄에 `|---|---|`. 줄글로 늘어놓지 마라."
    ),
    "why": (
        "- ★ 개념마다 **'왜 그런가'를 한 문장 이상 반드시 써라.** 정의만 적고 "
        "넘어가지 마라 — 결론만 남으면 이 학습자에게는 아무것도 안 남는다."
    ),
    # definition은 없다 — 원래 지시만으로 지켜진다(실측 4/4).
}


def style_block(style: str) -> str:
    """진단에서 고른 형식 → 프롬프트 블록. 모르는 값이면 빈 문자열.

    형식 지시 한 줄 + **그 형식에서 반드시 지킬 것** 한 줄(`_ENFORCE`).

    ⚠️ 화면 문구는 "당신에게 맞는 학습법"이 아니라 **"어떤 설명이 읽기 편한가"**
       였다. 러닝 스타일 맞춤에 학습 효과 근거는 없다(Pashler 2008) — 이건
       성취가 아니라 이탈을 막는 장치다. 여기 주석에도 남겨 둔다, 나중에
       이 값으로 효과를 주장하지 않도록.
    """
    key = (style or "").strip().lower()
    line = STYLE_DIRECTIVE.get(key)
    if not line:
        return ""
    keep = _ENFORCE.get(key, "")
    body = f"{line}\n{keep}" if keep else line
    return f"[이 학습자에게 맞춘 설명 방식]\n{body}"


def fixture_profile(name: str | None = None) -> Profile:
    """데모·온보딩 전용 성향. 평가 UI가 없을 때 생성에 쓸 고정값.

    환경변수 `CURRICULUM_PROFILE`:
      metaphor(기본)  비유·예시 선호 — 지시가 실제로 나가게 2회 관찰
      formal          정의·형식 선호
      neutral / none  빈 프로필(지시 없음)
    """
    import os

    key = (name if name is not None else os.getenv("CURRICULUM_PROFILE", "metaphor")).strip().lower()
    if key in ("", "neutral", "none", "off"):
        return empty_profile()
    p = empty_profile()
    if key in ("metaphor", "analogy", "example"):
        for _ in range(2):
            p = observe(p, "representation", True)
    elif key in ("formal", "definition"):
        for _ in range(2):
            p = observe(p, "representation", False)
    elif key == "deep":
        for _ in range(2):
            p = observe(p, "depth", True)
    elif key == "brief":
        for _ in range(2):
            p = observe(p, "depth", False)
    else:
        print(f"[curriculum] 모르는 CURRICULUM_PROFILE={key!r} — 중립으로 둔다")
        return empty_profile()
    return p


def explain(profile: Profile) -> list[str]:
    """화면의 ⚡ 표시에 쓸 사람 말. 실제로 적용된 축만 돌려준다.

    지시문과 같은 조건으로 만들어야 한다 — 화면에는 "비유를 먼저 씁니다"라고
    써놓고 프롬프트엔 안 들어가면 거짓말이 된다.
    """
    out: list[str] = []
    for axis in AXES:
        s = profile.get(axis.key, AxisScore())
        if not s.active:
            continue
        label = axis.high_label if s.score > HIGH else axis.low_label
        out.append(f"{label} 설명합니다")
    return out


def as_display(profile: Profile) -> list[dict]:
    """프로필 카드용 — 축마다 점수·신뢰도·적용 여부.

    신뢰도가 낮은 축도 보여주되 "아직 확실치 않음"으로 표시한다. 숨기면
    사용자가 왜 어떤 축은 반영되고 어떤 축은 아닌지 알 수 없다.
    """
    rows = []
    for axis in AXES:
        s = profile.get(axis.key, AxisScore())
        rows.append(
            {
                "key": axis.key,
                "low": axis.low_label,
                "high": axis.high_label,
                "score": s.score,
                "confidence": s.confidence,
                "n": s.n,
                "active": s.active,
            }
        )
    return rows
