import { useState } from "react";
import { clsx } from "clsx";

import type { AttemptResult, ExplainBackBlockData, OnAnswer } from "./types";

// ② 파인만 역질문 — 직접 설명 → 서버(Solar)가 rubric[] 키포인트 대조로 {score, feedback} 채점.
export function ExplainBackBlock({
  blockId,
  conceptId,
  data,
  onAnswer,
}: {
  blockId: string;
  conceptId: string;
  data: ExplainBackBlockData;
  onAnswer: OnAnswer;
}) {
  const [text, setText] = useState("");
  const [result, setResult] = useState<AttemptResult | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [tooShort, setTooShort] = useState(false);
  const done = result !== null;
  const passed = result?.correct === true;

  const submit = async () => {
    if (done || submitting) return;
    if (text.trim().length <= 5) {
      setTooShort(true);
      return;
    }
    setTooShort(false);
    setSubmitting(true);
    try {
      const r = await onAnswer({ blockId, conceptId, userInput: text.trim() });
      setResult(r);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div>
      <div className="mb-4 text-[1.1rem] font-semibold text-text-primary">{data.prompt}</div>
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        disabled={done}
        placeholder="예: 변수 선언은 빈 상자를 준비하는 거고..."
        className={clsx(
          "min-h-[120px] w-full resize-y rounded-xl border border-border-primary p-4 text-base leading-relaxed text-text-primary outline-none transition-colors placeholder:text-text-tertiary focus:border-accent",
          done && "bg-bg-secondary text-text-secondary",
        )}
      />
      {tooShort && (
        <p className="mt-2 text-[0.85rem] font-medium text-[#b91c1c]">내용을 조금 더 길게 작성해 주세요.</p>
      )}

      {done ? (
        <div
          className={clsx(
            "mt-4 rounded-xl p-4 text-[0.9rem] leading-relaxed",
            passed ? "bg-[#10b981]/10 text-[#047857]" : "bg-[#f59e0b]/10 text-[#b45309]",
          )}
        >
          <div className="mb-1 font-bold">
            {passed ? "✅" : "🟡"} AI 채점: {Math.round((result?.score ?? 0) * 100)}점
          </div>
          {result?.feedback?.comment && <p>{result.feedback.comment}</p>}
          {result?.feedback?.missedPoints && result.feedback.missedPoints.length > 0 && (
            <ul className="mt-2 list-disc pl-5 text-text-secondary">
              {result.feedback.missedPoints.map((p, i) => (
                <li key={i}>놓친 포인트: {p}</li>
              ))}
            </ul>
          )}
        </div>
      ) : (
        <div className="mt-4 flex justify-end">
          <button
            type="button"
            onClick={submit}
            disabled={submitting}
            className="rounded-xl bg-primary px-5 py-[0.6rem] text-[13.3333px] font-semibold leading-[normal] text-white shadow-sm transition-all hover:-translate-y-0.5 hover:bg-primary-hover hover:shadow-md disabled:opacity-50"
          >
            {submitting ? "채점 중…" : "제출 및 피드백 받기"}
          </button>
        </div>
      )}
    </div>
  );
}
