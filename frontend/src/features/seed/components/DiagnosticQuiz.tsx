import { useState } from "react";

import type { AnswerItem, DiagnosticQuestion } from "@/features/seed/types";
import { isPrerequisiteConceptId } from "@/features/seed/types";
import { GenerationBanner } from "@/features/seed/components/GenerationBanner";
import { Button } from "@/shared/ui/Button";

interface Props {
  questions: DiagnosticQuestion[];
  prerequisiteCount?: number;
  onSubmit: (answers: AnswerItem[]) => void;
  isPending: boolean;
  error: string | null;
  generationMode?: "llm" | "fallback";
  generationNote?: string | null;
}

function QuestionBadge({ isPrereq }: { isPrereq: boolean }) {
  return (
    <span
      style={{
        display: "inline-block",
        marginRight: 6,
        padding: "1px 7px",
        borderRadius: 4,
        fontSize: "0.72rem",
        fontWeight: 700,
        background: isPrereq ? "#ede7f6" : "#e8f4fd",
        color: isPrereq ? "#5e35b1" : "#1565c0",
        border: `1px solid ${isPrereq ? "#b39ddb" : "#90caf9"}`,
      }}
    >
      {isPrereq ? "사전지식" : "PDF 개념"}
    </span>
  );
}

function FormatBadge({ questionType }: { questionType: DiagnosticQuestion["question_type"] }) {
  const isOpen = questionType === "open_ended";
  return (
    <span
      style={{
        display: "inline-block",
        marginRight: 6,
        padding: "1px 7px",
        borderRadius: 4,
        fontSize: "0.72rem",
        fontWeight: 700,
        background: isOpen ? "#fff3e0" : "#f1f8e9",
        color: isOpen ? "#e65100" : "#33691e",
        border: `1px solid ${isOpen ? "#ffcc80" : "#c5e1a5"}`,
      }}
    >
      {isOpen ? "서술형 · 인출" : "4지선다"}
    </span>
  );
}

export function DiagnosticQuiz({
  questions,
  prerequisiteCount = 0,
  onSubmit,
  isPending,
  error,
  generationMode,
  generationNote,
}: Props) {
  const [choices, setChoices] = useState<Record<string, number>>({});
  const [textAnswers, setTextAnswers] = useState<Record<string, string>>({});

  const answeredCount = questions.filter((q) => {
    if (q.question_type === "open_ended") {
      return Boolean(textAnswers[q.id]?.trim());
    }
    return choices[q.id] !== undefined;
  }).length;

  const allAnswered = answeredCount === questions.length;

  const handleSubmit = () => {
    const answers: AnswerItem[] = questions.map((q) => {
      if (q.question_type === "open_ended") {
        return { question_id: q.id, text_response: textAnswers[q.id]?.trim() ?? "" };
      }
      return { question_id: q.id, choice_index: choices[q.id] ?? 0 };
    });
    onSubmit(answers);
  };

  return (
    <section>
      <h2>2. 진단 평가</h2>
      <GenerationBanner mode={generationMode} note={generationNote} />
      <p style={{ color: "#555" }}>
        Solar가 추출한 사전지식({prerequisiteCount}개)과 PDF 개념을 확인합니다. 4지선다와{" "}
        <strong>서술형(기억에서 꺼내 설명)</strong>이 섞여 있습니다. ({answeredCount}/
        {questions.length} 응답)
      </p>

      <ol style={{ paddingLeft: "1.25rem", marginTop: "1rem" }}>
        {questions.map((q, idx) => {
          const isPrereq = isPrerequisiteConceptId(q.concept_id);
          const isOpen = q.question_type === "open_ended";
          return (
            <li key={q.id} style={{ marginBottom: "1.25rem" }}>
              <p>
                <strong>Q{idx + 1}.</strong>{" "}
                <QuestionBadge isPrereq={isPrereq} />
                <FormatBadge questionType={q.question_type} />
                {q.question_text}
              </p>

              {isOpen ? (
                <textarea
                  value={textAnswers[q.id] ?? ""}
                  onChange={(e) =>
                    setTextAnswers((prev) => ({ ...prev, [q.id]: e.target.value }))
                  }
                  placeholder="기억나는 대로 자신의 말로 설명해 보세요..."
                  rows={4}
                  style={{
                    width: "100%",
                    marginTop: 8,
                    padding: "0.65rem 0.75rem",
                    borderRadius: 8,
                    border: "1px solid #ccc",
                    fontSize: "0.92rem",
                    resize: "vertical",
                    boxSizing: "border-box",
                  }}
                />
              ) : (
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
              )}
            </li>
          );
        })}
      </ol>

      <Button disabled={!allAnswered || isPending} onClick={handleSubmit}>
        {isPending ? "채점 중..." : "제출"}
      </Button>
      {error && <p style={{ color: "crimson", marginTop: "0.75rem" }}>{error}</p>}
    </section>
  );
}
