"""성향 프로파일 순수 로직 — 축 정의·신호 반영(EMA)·생성 지시문·표시 라벨.

DB/LLM 의존 없음. 준거(재설계 브리프 §2):
  - 성향은 "어떻게 배우는가"의 축 — 내용 범위·분량은 절대 건드리지 않는다.
  - 지시문 변환은 결정적(임계값 기반)이어야 한다. LLM에 "이 사람은 비유파니까
    알아서"라고 맡기면 반영 여부를 검증할 수 없다.

축 (0..1 연속 점수, 브리프 §2.1의 예시 4종을 사상):
  representation  0=형식적 정의·기호 우선   ↔  1=비유·구체 예시 우선
  rigor           0=일단 암기하고 진행      ↔  1=근본이 이해돼야 넘어감
  context         0=본론·핵심 직행          ↔  1=왜/어디서 나왔는지 맥락 필요
"""
from __future__ import annotations

from dataclasses import dataclass

AXES = ("representation", "rigor", "context")

# 지시문 발동 임계값. confidence가 낮으면(측정 부족) 지시문을 아예 안 쓴다 —
# 잘못 잰 성향으로 세게 미는 것보다 중립 생성이 낫다.
_HIGH = 0.6
_LOW = 0.4
_MIN_CONFIDENCE = 0.35


@dataclass(frozen=True)
class AxisState:
    score: float = 0.5
    confidence: float = 0.0
    n: int = 0


def _clamp01(v: float) -> float:
    return max(0.0, min(1.0, v))


def apply_signal(state: AxisState, signal: float) -> AxisState:
    """신호 1건 반영 — EMA. 초기엔 빠르게 수렴, 이후 천천히 표류.

    성향은 "거의" 고정이지 완전 고정이 아니므로 k에 하한(0.15)을 둬
    학습 중 행동 신호가 계속 반영될 여지를 남긴다.
    """
    k = max(0.15, 1.0 / (state.n + 1))
    score = _clamp01((1 - k) * state.score + k * _clamp01(signal))
    n = state.n + 1
    confidence = min(0.9, 0.3 + 0.15 * n)
    return AxisState(score=round(score, 4), confidence=round(confidence, 4), n=n)


def compute_axes(events: list[dict]) -> dict[str, dict]:
    """evidence 이벤트 로그 → 축 상태. 이벤트: {"axis": str, "signal": float, ...}.

    manual(사용자 직접 수정) 이벤트는 그 시점 이후의 기준점이 된다 —
    측정이 틀렸을 때 사용자가 시스템과 싸우지 않게 하는 안전판.
    """
    states: dict[str, AxisState] = {a: AxisState() for a in AXES}
    for e in events:
        axis = e.get("axis")
        if axis not in states:
            continue
        if e.get("source") == "manual":
            prev = states[axis]
            states[axis] = AxisState(
                score=_clamp01(float(e.get("signal", 0.5))),
                confidence=0.9,
                n=max(prev.n, 1),
            )
        else:
            states[axis] = apply_signal(states[axis], float(e.get("signal", 0.5)))
    return {
        a: {"score": s.score, "confidence": s.confidence, "n": s.n}
        for a, s in states.items()
    }


# ── 성향 → 생성 지시문 (결정적 변환) ─────────────────────────────────
# 불변 조건(준거 §2.2 가드): 지시문은 설명의 '모양'만 바꾼다. 근거 발췌·
# 블록 커버리지·인출 문항 수 같은 '양'은 여기서 언급조차 하지 않는다.
_DIRECTIVES: dict[str, dict[str, str]] = {
    "representation": {
        "high": "- 정의보다 실생활 비유·구체 예시를 먼저 제시하고, 형식적 정의는 그 뒤에 정리하라. analogy 블록을 반드시 1개 포함하라.",
        "low": "- 정확한 정의와 형식적 서술을 앞세우고, 예시는 정의를 뒷받침하는 보조로만 써라.",
    },
    "rigor": {
        "high": "- 결과·공식만 주지 말고 왜 그렇게 되는지 유도·원리를 단계적으로 전개하라.",
        "low": "- 핵심 요약과 기억을 돕는 장치(니모닉·정리 표현)를 먼저 주고, 원리 설명은 간결하게 하라.",
    },
    "context": {
        "high": "- 이 개념이 왜 필요했고 어떤 문제에서 나왔는지 동기·맥락으로 설명을 시작하라. whyItMatters를 충실히 써라.",
        "low": "- 배경 서사 없이 본론(정의·동작)부터 곧장 들어가라. whyItMatters는 한 문장으로 간결하게.",
    },
}


def directive_from_axes(axes: dict | None) -> str:
    """축 상태 → 프롬프트 지시문. 프로파일 없음/신뢰도 부족이면 빈 문자열(중립 생성)."""
    if not axes:
        return ""
    lines: list[str] = []
    for axis in AXES:
        state = axes.get(axis) or {}
        score = float(state.get("score", 0.5))
        confidence = float(state.get("confidence", 0.0))
        if confidence < _MIN_CONFIDENCE:
            continue
        if score >= _HIGH:
            lines.append(_DIRECTIVES[axis]["high"])
        elif score <= _LOW:
            lines.append(_DIRECTIVES[axis]["low"])
    if not lines:
        return ""
    return (
        "[학습자 성향 — 설명 방식만 이에 맞춰 조정하라. 내용의 범위·깊이·분량은 줄이지 마라]\n"
        + "\n".join(lines)
    )


# ── 표시 라벨 (프로필 카드용 파생값) ─────────────────────────────────
def profile_label(axes: dict | None) -> tuple[str, list[str]]:
    """축 상태 → (한 줄 라벨, 특성 설명 목록). 내부 판단엔 쓰지 않는 표시 전용."""
    axes = axes or {}

    def score(axis: str) -> float:
        return float((axes.get(axis) or {}).get("score", 0.5))

    traits: list[str] = []
    if score("representation") >= _HIGH:
        traits.append("비유와 예시로 개념을 붙잡는 편이에요.")
    elif score("representation") <= _LOW:
        traits.append("정확한 정의와 원리부터 짚는 편이에요.")
    if score("rigor") >= _HIGH:
        traits.append("근본이 이해돼야 다음으로 넘어가는 편이에요.")
    elif score("rigor") <= _LOW:
        traits.append("일단 부딪히며 진도를 나가는 실전형이에요.")
    if score("context") >= _HIGH:
        traits.append("'왜 이게 나왔지?' 맥락이 잡혀야 이해가 깊어져요.")
    elif score("context") <= _LOW:
        traits.append("배경 설명보다 본론과 핵심을 선호해요.")

    # 라벨: 가장 뚜렷한 축 우선으로 수식어를 조합
    rep, rig, ctx = score("representation"), score("rigor"), score("context")
    front = "비유로 이해하는" if rep >= _HIGH else ("원리로 파고드는" if rep <= _LOW else "균형 잡힌")
    back = "탐구자" if rig >= _HIGH else ("실전가" if rig <= _LOW else "학습자")
    if ctx >= _HIGH:
        back = f"맥락형 {back}"
    label = f"{front} {back}"
    if not traits:
        traits.append("아직 뚜렷한 성향이 잡히지 않았어요. 학습하면서 계속 정교해져요.")
    return label, traits
