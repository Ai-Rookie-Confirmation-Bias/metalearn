import { useMemo, useState } from "react";
import { clsx } from "clsx";

import type { AttemptResult, ClozeBlockData, OnAnswer } from "./types";

const norm = (s: string) => s.trim().toLowerCase();

// ② 빈칸 채우기 — 정답은 스트립됨(서버 채점). 모든 빈칸 입력 후 "확인" → 라운드트립 채점.
// 채점 응답의 reveal.blanks로 빈칸별 정오를 표시한다.
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
  const [values, setValues] = useState<Record<number, string>>({});
  const [result, setResult] = useState<AttemptResult | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const locked = result?.correct === true;

  const ordered = useMemo(
    () => Array.from({ length: blankCount }, (_, i) => values[i] ?? ""),
    [values, blankCount],
  );
  const filled = ordered.every((v) => v.trim().length > 0);

  const submit = async () => {
    if (!filled || locked || submitting) return;
    setSubmitting(true);
    setResult(null);
    try {
      const r = await onAnswer({ blockId, conceptId, userInput: ordered });
      setResult(r);
    } finally {
      setSubmitting(false);
    }
  };

  // 채점 후 빈칸별 정오 — reveal.blanks와 대조(대소문자/공백 무시)
  const blankState = (idx: number): "idle" | "correct" | "incorrect" => {
    if (!result) return "idle";
    const ans = result.reveal?.blanks?.[idx];
    if (ans === undefined) return result.correct ? "correct" : "incorrect";
    return norm(values[idx] ?? "") === norm(ans) ? "correct" : "incorrect";
  };

  let blankIdx = -1;
  return (
    <div>
      <div className="text-[1.1rem] leading-[2] text-text-primary">
        {data.segments.map((seg, i) => {
          if (seg.kind === "text") {
            return seg.text.split(/`(.+?)`/g).map((p, j) =>
              j % 2 === 1 ? (
                <code
                  key={`${i}-${j}`}
                  className="rounded bg-bg-secondary px-1.5 py-0.5 font-mono text-[0.95rem]"
                >
                  {p}
                </code>
              ) : (
                <span key={`${i}-${j}`}>{p}</span>
              ),
            );
          }
          blankIdx += 1;
          const idx = blankIdx;
          const st = blankState(idx);
          return (
            <input
              key={i}
              type="text"
              value={values[idx] ?? ""}
              onChange={(e) =>
                setValues((prev) => ({ ...prev, [idx]: e.target.value }))
              }
              placeholder="?"
              disabled={locked}
              className={clsx(
                "mx-1.5 inline-block h-8 min-w-[80px] rounded-md border px-2 text-center align-middle font-semibold outline-none transition-all",
                st === "idle" &&
                  "border-dashed border-text-tertiary bg-bg-secondary focus:border-solid focus:border-accent focus:bg-white",
                st === "correct" &&
                  "border-solid border-[#10b981] bg-[#10b981]/10 text-[#047857]",
                st === "incorrect" &&
                  "border-solid border-[#ef4444] bg-[#ef4444]/10 text-[#b91c1c]",
              )}
            />
          );
        })}
      </div>

      {!locked && (
        <button
          type="button"
          onClick={submit}
          disabled={!filled || submitting}
          className="mt-4 rounded-xl bg-primary px-5 py-2 text-[0.9rem] font-semibold text-white shadow-sm transition-all hover:bg-primary-hover disabled:cursor-not-allowed disabled:opacity-50"
        >
          {submitting ? "채점 중…" : "확인"}
        </button>
      )}
      {result && !result.correct && (
        <div className="mt-3 text-[0.9rem] font-medium text-[#b91c1c]">
          틀린 빈칸이 있어요. 다시 시도해보세요.
        </div>
      )}
    </div>
  );
}
