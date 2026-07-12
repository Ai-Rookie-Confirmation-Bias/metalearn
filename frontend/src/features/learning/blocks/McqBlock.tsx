import { useState } from "react";
import { clsx } from "clsx";

import type { AttemptResult, McqBlockData, OnAnswer } from "./types";

// ② 객관식 — 첫 선택이 확정(정답이든 오답이든 못 바꿈). 채점 후 정답(초록)·오답(빨강)
// 표시 + 해설. 인출 학습은 '맞혀야 통과'가 아니라 '풀면 진행'이라, 오답도 그대로 기록된다.
export function McqBlock({
  blockId,
  conceptId,
  data,
  onAnswer,
}: {
  blockId: string;
  conceptId: string;
  data: McqBlockData;
  onAnswer: OnAnswer;
}) {
  const [picked, setPicked] = useState<number | null>(null);
  const [locked, setLocked] = useState(false); // 첫 선택 후 잠금(변경 불가)
  const [result, setResult] = useState<AttemptResult | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // 라운드트립: 클라는 정답을 모름(스트립) → userInput만 보내고 서버 채점 결과로 표시.
  const pick = async (i: number) => {
    if (locked || submitting) return;
    setPicked(i);
    setResult(null);
    setSubmitting(true);
    try {
      const r = await onAnswer({ blockId, conceptId, userInput: i });
      setResult(r);
      setLocked(true); // 정답/오답 무관 — 첫 선택으로 확정
    } finally {
      setSubmitting(false);
    }
  };

  const correctIdx = result?.reveal?.answerIndex ?? null;

  return (
    <div>
      <div className="mb-6 text-[1.1rem] font-semibold text-text-primary">{data.question}</div>
      <div className="flex flex-col gap-3">
        {data.options.map((opt, i) => {
          // 채점 후: 정답 보기는 초록, 내가 고른 오답은 빨강, 나머지는 idle.
          const state = !result
            ? picked === i
              ? "picked"
              : "idle"
            : correctIdx === i
              ? "correct"
              : picked === i
                ? "incorrect"
                : "idle";
          return (
            <button
              key={i}
              type="button"
              onClick={() => pick(i)}
              disabled={locked || submitting}
              className={clsx(
                "flex items-center gap-4 rounded-xl border px-5 py-4 text-left text-[0.95rem] transition-all",
                state === "idle" &&
                  "border-border-primary bg-white text-text-primary hover:border-accent hover:bg-accent/[0.02]",
                state === "picked" && "border-accent bg-accent/[0.06] text-text-primary",
                state === "correct" && "border-[#10b981] bg-[#10b981]/10 font-semibold text-[#047857]",
                state === "incorrect" && "border-[#ef4444] bg-[#ef4444]/10 text-[#b91c1c]",
                locked && "cursor-default",
              )}
            >
              <span
                className={clsx(
                  "flex h-6 w-6 shrink-0 items-center justify-center rounded-full border text-[0.8rem] font-bold",
                  state === "correct"
                    ? "border-[#10b981] bg-[#10b981] text-white"
                    : state === "incorrect"
                      ? "border-[#ef4444] text-[#b91c1c]"
                      : "border-border-primary text-text-tertiary",
                )}
              >
                {String.fromCharCode(65 + i)}
              </span>
              <span>{opt}</span>
            </button>
          );
        })}
      </div>

      {/* 채점 결과 — 정오 상태 한 줄 */}
      {result && (
        <div
          className={clsx(
            "mt-4 text-[0.9rem] font-semibold",
            result.correct ? "text-[#047857]" : "text-[#b91c1c]",
          )}
        >
          {result.correct
            ? "✅ 정답이에요!"
            : correctIdx !== null
              ? `❌ 오답이에요. 정답은 ${String.fromCharCode(65 + correctIdx)}번이에요.`
              : "❌ 오답이에요."}
        </div>
      )}

      {/* 해설 — 정답/오답 모두 노출(왜 그런지 배운다). 줄바꿈 보존(텍스트 벽 방지) */}
      {result && data.explanation && (
        <div className="mt-3 whitespace-pre-wrap break-keep rounded-xl bg-bg-secondary p-4 text-[0.9rem] leading-relaxed text-text-secondary">
          💡 {data.explanation}
        </div>
      )}
      {result && !data.explanation && result.reveal?.explanation && (
        <div className="mt-3 whitespace-pre-wrap break-keep rounded-xl bg-bg-secondary p-4 text-[0.9rem] leading-relaxed text-text-secondary">
          💡 {result.reveal.explanation}
        </div>
      )}
    </div>
  );
}
