import { useState } from "react";
import { clsx } from "clsx";

import type { McqBlockData, OnAnswer } from "./types";

// ② 객관식 — idle → 선택 → correct(초록, 잠금)/incorrect(빨강, 재시도 가능) + 해설
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
  const [locked, setLocked] = useState(false); // 정답 맞추면 잠금

  const pick = (i: number) => {
    if (locked) return;
    setPicked(i);
    const correct = i === data.answerIndex;
    if (correct) setLocked(true);
    onAnswer({ blockId, conceptId, correct, userInput: i });
  };

  return (
    <div>
      <div className="mb-6 text-[1.1rem] font-semibold text-text-primary">{data.question}</div>
      <div className="flex flex-col gap-3">
        {data.options.map((opt, i) => {
          const isPicked = picked === i;
          const state = !isPicked ? "idle" : i === data.answerIndex ? "correct" : "incorrect";
          return (
            <button
              key={i}
              type="button"
              onClick={() => pick(i)}
              className={clsx(
                "flex items-center gap-4 rounded-xl border px-5 py-4 text-left text-[0.95rem] transition-all",
                state === "idle" &&
                  "border-border-primary bg-white text-text-primary hover:border-accent hover:bg-accent/[0.02]",
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
      {locked && data.explanation && (
        <div className="mt-4 rounded-xl bg-bg-secondary p-4 text-[0.9rem] leading-relaxed text-text-secondary">
          💡 {data.explanation}
        </div>
      )}
    </div>
  );
}
