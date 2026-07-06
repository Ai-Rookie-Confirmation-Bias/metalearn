import { useState } from "react";
import { clsx } from "clsx";

import type { ClozeBlockData, OnAnswer } from "./types";

type BlankState = "idle" | "correct" | "incorrect";

// 빈칸 하나 — 원본 .cloze-blank: 점선 → 포커스 실선 → 정답 초록(잠금)/오답 빨강
function Blank({
  answer,
  aliases,
  onResult,
}: {
  answer: string;
  aliases?: string[];
  onResult: (correct: boolean, value: string) => void;
}) {
  const [value, setValue] = useState("");
  const [state, setState] = useState<BlankState>("idle");
  const accepted = [answer, ...(aliases ?? [])];

  const handle = (v: string) => {
    setValue(v);
    const t = v.trim();
    if (accepted.includes(t)) {
      setState("correct");
      onResult(true, t);
    } else if (t.length >= answer.length) {
      setState("incorrect");
      onResult(false, t);
    } else {
      setState("idle");
    }
  };

  return (
    <input
      type="text"
      value={value}
      onChange={(e) => handle(e.target.value)}
      placeholder="?"
      disabled={state === "correct"}
      className={clsx(
        "mx-1.5 inline-block h-8 min-w-[80px] rounded-md border px-2 text-center align-middle font-semibold outline-none transition-all",
        state === "idle" &&
          "border-dashed border-text-tertiary bg-bg-secondary focus:border-solid focus:border-accent focus:bg-white",
        state === "correct" && "border-solid border-[#10b981] bg-[#10b981]/10 text-[#047857]",
        state === "incorrect" && "border-solid border-[#ef4444] bg-[#ef4444]/10 text-[#b91c1c]",
      )}
    />
  );
}

// ② 빈칸 채우기 — 문장 속 인라인 input. 모든 빈칸이 맞으면 onAnswer(correct)
export function ClozeBlock({
  blockId,
  conceptId,
  data,
  onAnswer,
}: {
  blockId: string;
  conceptId: string;
  data: ClozeBlockData;
  onAnswer: OnAnswer;
}) {
  const blankCount = data.segments.filter((s) => s.kind === "blank").length;
  const [solved, setSolved] = useState<Record<number, string>>({});

  const onResult = (idx: number) => (correct: boolean, value: string) => {
    if (!correct) return;
    const next = { ...solved, [idx]: value };
    setSolved(next);
    if (Object.keys(next).length === blankCount) {
      onAnswer({ blockId, conceptId, correct: true, userInput: next });
    }
  };

  let blankIdx = -1;
  return (
    <div className="text-[1.1rem] leading-[2] text-text-primary">
      {data.segments.map((seg, i) => {
        if (seg.kind === "text") {
          // 개행과 `코드` 표기 최소 지원
          return seg.text.split(/`(.+?)`/g).map((p, j) =>
            j % 2 === 1 ? (
              <code key={`${i}-${j}`} className="rounded bg-bg-secondary px-1.5 py-0.5 font-mono text-[0.95rem]">
                {p}
              </code>
            ) : (
              <span key={`${i}-${j}`}>{p}</span>
            ),
          );
        }
        blankIdx += 1;
        const idx = blankIdx;
        return <Blank key={i} answer={seg.answer} aliases={seg.aliases} onResult={onResult(idx)} />;
      })}
    </div>
  );
}
