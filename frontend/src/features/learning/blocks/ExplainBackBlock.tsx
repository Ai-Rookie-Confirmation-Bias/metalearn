import { useState } from "react";
import { clsx } from "clsx";

import type { ExplainBackBlockData, OnAnswer } from "./types";

// ② 파인만 역질문 — 직접 설명하게 하고 채점.
// ⚠️ 실제 채점은 서버(Solar)가 rubric[] 키포인트 대조로 {score, feedback} 반환 (POST /attempts).
//    지금은 mock: 최소 길이만 확인하고 통과 피드백.
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
  const [state, setState] = useState<"idle" | "tooShort" | "done">("idle");

  const submit = () => {
    if (state === "done") return;
    if (text.trim().length <= 5) {
      setState("tooShort");
      return;
    }
    setState("done");
    onAnswer({ blockId, conceptId, correct: true, userInput: text.trim() });
  };

  return (
    <div>
      <div className="mb-4 text-[1.1rem] font-semibold text-text-primary">{data.prompt}</div>
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        disabled={state === "done"}
        placeholder="예: 변수 선언은 빈 상자를 준비하는 거고..."
        className={clsx(
          "min-h-[120px] w-full resize-y rounded-xl border border-border-primary p-4 text-base leading-relaxed text-text-primary outline-none transition-colors placeholder:text-text-tertiary focus:border-accent",
          state === "done" && "bg-bg-secondary text-text-secondary",
        )}
      />
      {state === "tooShort" && (
        <p className="mt-2 text-[0.85rem] font-medium text-[#b91c1c]">내용을 조금 더 길게 작성해 주세요.</p>
      )}
      {state === "done" ? (
        <div className="mt-4 rounded-xl bg-[#10b981]/10 p-4 text-[0.9rem] font-medium leading-relaxed text-[#047857]">
          ✅ AI 피드백: 아주 훌륭한 비유입니다! 핵심을 잘 짚었어요.
        </div>
      ) : (
        <div className="mt-4 flex justify-end">
          <button
            type="button"
            onClick={submit}
            className="rounded-xl bg-primary px-5 py-[0.6rem] text-[13.3333px] font-semibold leading-[normal] text-white shadow-sm transition-all hover:-translate-y-0.5 hover:bg-primary-hover hover:shadow-md"
          >
            제출 및 피드백 받기
          </button>
        </div>
      )}
    </div>
  );
}
