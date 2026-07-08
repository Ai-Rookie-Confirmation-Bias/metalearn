"""성향 프로파일 순수 로직 단위 테스트."""
from app.features.profile.logic import (
    AXES,
    AxisState,
    apply_signal,
    compute_axes,
    directive_from_axes,
    profile_label,
)


def test_apply_signal_converges_high():
    s = AxisState()
    for _ in range(5):
        s = apply_signal(s, 1.0)
    assert s.score > 0.9
    assert s.n == 5
    assert s.confidence >= 0.3


def test_manual_event_overrides():
    events = [
        {"source": "onboarding", "axis": "rigor", "signal": 0.0},
        {"source": "manual", "axis": "rigor", "signal": 0.85},
    ]
    axes = compute_axes(events)
    assert axes["rigor"]["score"] == 0.85
    assert axes["rigor"]["confidence"] == 0.9


def test_directive_low_confidence_empty():
    assert directive_from_axes({"representation": {"score": 0.9, "confidence": 0.2, "n": 1}}) == ""


def test_directive_high_representation():
    d = directive_from_axes({"representation": {"score": 0.75, "confidence": 0.5, "n": 3}})
    assert "비유" in d


def test_profile_label_has_traits():
    axes = {a: {"score": 0.75, "confidence": 0.5, "n": 3} for a in AXES}
    label, traits = profile_label(axes)
    assert label
    assert traits
