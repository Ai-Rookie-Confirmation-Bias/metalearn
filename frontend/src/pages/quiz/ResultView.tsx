import { Link } from "react-router-dom";
import { ArrowCounterClockwiseIcon, ListChecksIcon, BookOpenIcon } from "@phosphor-icons/react";

import type { SolveResult } from "./SolveView";

// 화면 3: 결과 — 확정안 §6-3. 목차별 정답률 바 + 세 버튼.
// [학습 시작하기]가 학습 페이지로 가는 유일한 연결 — 사람만 넘어가고 데이터는 안 넘어감.
export function ResultView({
  results,
  tocTitles,
  onRetry,
  onChangeScope,
}: {
  results: SolveResult[];
  tocTitles: Record<number, string>;
  onRetry: () => void;
  onChangeScope: () => void;
}) {
  const total = results.length;
  const correct = results.filter((r) => r.correct).length;

  // 목차별 집계
  const byToc = new Map<number, { correct: number; total: number }>();
  for (const r of results) {
    const acc = byToc.get(r.tocIndex) ?? { correct: 0, total: 0 };
    acc.total += 1;
    if (r.correct) acc.correct += 1;
    byToc.set(r.tocIndex, acc);
  }

  return (
    <div className="mx-auto w-full max-w-[720px] p-12">
      <div className="rounded-2xl border border-border-primary bg-white p-8 shadow-sm">
        <h2 className="mb-8 text-center text-2xl font-extrabold text-primary">
          📝 {total}문항 · {correct}정답
        </h2>

        <div className="mb-8 flex flex-col gap-4">
          {[...byToc.entries()].map(([tocIndex, acc]) => {
            const pct = Math.round((acc.correct / acc.total) * 100);
            return (
              <div key={tocIndex}>
                <div className="mb-1.5 flex items-center justify-between text-[0.9rem]">
                  <span className="font-semibold text-text-primary">{tocTitles[tocIndex]}</span>
                  <span className="text-text-secondary">
                    {acc.correct}/{acc.total} · {pct}%
                  </span>
                </div>
                <div className="h-2.5 overflow-hidden rounded-full bg-border-primary">
                  <div
                    className="h-full rounded-full bg-accent transition-all duration-500"
                    style={{ width: `${pct}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>

        <div className="flex flex-wrap items-center justify-center gap-3 border-t border-border-primary pt-6">
          <button
            type="button"
            onClick={onRetry}
            className="inline-flex items-center gap-2 rounded-xl border border-border-primary bg-bg-secondary px-4 py-2 text-[0.85rem] font-semibold text-text-primary transition-colors hover:bg-border-primary/50"
          >
            <ArrowCounterClockwiseIcon /> 다시 풀기
          </button>
          <button
            type="button"
            onClick={onChangeScope}
            className="inline-flex items-center gap-2 rounded-xl border border-border-primary bg-bg-secondary px-4 py-2 text-[0.85rem] font-semibold text-text-primary transition-colors hover:bg-border-primary/50"
          >
            <ListChecksIcon /> 다른 범위
          </button>
          <Link
            to="/learning"
            className="inline-flex items-center gap-2 rounded-xl bg-primary px-5 py-[0.6rem] text-[13.3333px] font-semibold leading-[normal] text-white shadow-sm transition-all hover:-translate-y-0.5 hover:bg-primary-hover hover:shadow-md"
          >
            <BookOpenIcon weight="fill" /> 학습 시작하기
          </Link>
        </div>
      </div>
    </div>
  );
}
