import { useState } from "react";

import type { DiagnosticQuestion } from "@/features/seed/types";
import { GenerationBanner } from "@/features/seed/components/GenerationBanner";
import { Button } from "@/shared/ui/Button";

interface Props {
  questions: DiagnosticQuestion[];
  onSubmit: (choices: Record<string, number>) => void;
  isPending: boolean;
  error: string | null;
  generationMode?: "llm" | "fallback";
  generationNote?: string | null;
}

export function DiagnosticQuiz({
  questions,
  onSubmit,
  isPending,
  error,
  generationMode,
  generationNote,
}: Props) {
  const [choices, setChoices] = useState<Record<string, number>>({});

  const allAnswered = questions.every((q) => choices[q.id] !== undefined);

  return (
    <section>
      <h2>3. 진단 평가</h2>
      <GenerationBanner mode={generationMode} note={generationNote} />
      <p style={{ color: "#555" }}>
        학습 범위 개념을 확인합니다. ({Object.keys(choices).length}/{questions.length} 응답)
      </p>

      <ol style={{ paddingLeft: "1.25rem", marginTop: "1rem" }}>
        {questions.map((q, idx) => (
          <li key={q.id} style={{ marginBottom: "1.25rem" }}>
            <p>
              <strong>Q{idx + 1}.</strong> [{q.concept_id}] {q.question_text}
            </p>
            <div style={{ display: "flex", flexDirection: "column", gap: 6, marginTop: 8 }}>
              {q.options.map((opt, i) => (
                <label key={i} style={{ cursor: "pointer" }}>
                  <input
                    type="radio"
                    name={q.id}
                    checked={choices[q.id] === i}
                    onChange={() => setChoices((prev) => ({ ...prev, [q.id]: i }))}
                  />{" "}
                  {opt.length > 120 ? `${opt.slice(0, 120)}…` : opt}
                </label>
              ))}
            </div>
          </li>
        ))}
      </ol>

      <Button disabled={!allAnswered || isPending} onClick={() => onSubmit(choices)}>
        {isPending ? "채점 중..." : "제출"}
      </Button>
      {error && <p style={{ color: "crimson", marginTop: "0.75rem" }}>{error}</p>}
    </section>
  );
}
