import type { DiagnosticResult, SeedSlice } from "@/features/seed/types";
import { LEARNING_GOAL_LABELS, type LearningGoal } from "@/features/seed/types";
import { Button } from "@/shared/ui/Button";

interface Props {
  result: DiagnosticResult;
  slice: SeedSlice;
  onReset: () => void;
}

export function SeedResult({ result, slice, onReset }: Props) {
  const goalLabel =
    slice.learning_goal && slice.learning_goal in LEARNING_GOAL_LABELS
      ? LEARNING_GOAL_LABELS[slice.learning_goal as LearningGoal]
      : slice.learning_goal ?? "—";

  return (
    <section>
      <h2>4. Seed 슬라이스 완료</h2>
      <p>
        점수: <strong>{Math.round(result.score * 100)}%</strong> · 약점 {result.weaknesses.length}
        개
      </p>

      {result.weaknesses.length > 0 && (
        <p style={{ color: "#a40" }}>
          약점 개념: {result.weaknesses.join(", ")}
        </p>
      )}

      <pre
        style={{
          background: "#f6f6f6",
          padding: "1rem",
          borderRadius: 8,
          overflow: "auto",
          fontSize: "0.85rem",
        }}
      >
        {JSON.stringify(
          {
            ...slice,
            learning_goal_label: goalLabel,
          },
          null,
          2,
        )}
      </pre>

      <Button onClick={onReset} style={{ marginTop: "1rem" }}>
        처음부터 다시
      </Button>
    </section>
  );
}
