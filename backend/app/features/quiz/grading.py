"""⑧ 서버 채점 — core/quality/grading으로 이동, 여기선 재노출만 (하위 호환)."""
from app.core.quality.grading import answer_payload, chosen_explanation, grade

__all__ = ["grade", "answer_payload", "chosen_explanation"]
