import { Link } from "react-router-dom";
import {
  ArrowCounterClockwiseIcon,
  ListChecksIcon,
  BookOpenIcon,
  SparkleIcon,
  CircleNotchIcon,
  CheckCircleIcon,
  InfoIcon,
} from "@phosphor-icons/react";

import type { SolveResult } from "./SolveView";

// 화면 3: 결과 — 확정안 §6-3. 목차별 정답률 바 + 세 버튼.
// [학습 시작하기]가 학습 페이지로 가는 유일한 연결 — 사람만 넘어가고 데이터는 안 넘어감.
// poolLow: 이 범위의 안 푼 문제가 바닥남 → "새 문제 만들기" 제안 카드 노출.
// 세션이 끝난 직후가 다음 행동을 제안할 최적 시점이라 결과 화면에 둔다.
export function ResultView({
  results,
  tocTitles,
  poolLow = false,
  refillState = "idle",
  refillOutcome = null,
  onRefill,
  onRetry,
  onChangeScope,
}: {
  results: SolveResult[];
  tocTitles: Record<number, string>;
  poolLow?: boolean;
  refillState?: "idle" | "requested";
  // 직전 리필의 결과 — 숫자(추가된 문항 수, 0이면 빈손) 또는 "failed".
  // null이면 보여줄 결과 없음. 진행 중(requested)보다 후순위로 그린다.
  refillOutcome?: number | "failed" | null;
  onRefill?: () => void;
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

        {/* 리필 완료 결과 — 성공(초록 확인)·빈손(재시도 말리는 안내)·실패.
            빈손·실패여도 버튼은 남긴다(A안): 강제로 막을 근거는 없고, 문구가
            비용을 설명한다. */}
        {refillState === "idle" && refillOutcome !== null && (
          <div
            className={
              typeof refillOutcome === "number" && refillOutcome > 0
                ? "mb-8 flex items-start gap-3 rounded-xl border border-[#10b981]/40 bg-[#10b981]/[0.06] p-5 text-[0.9rem] leading-relaxed"
                : "mb-8 flex items-start gap-3 rounded-xl bg-bg-secondary p-5 text-[0.9rem] leading-relaxed"
            }
          >
            {typeof refillOutcome === "number" && refillOutcome > 0 ? (
              <>
                <CheckCircleIcon weight="fill" className="mt-0.5 shrink-0 text-lg text-[#10b981]" />
                <div>
                  <div className="font-bold text-[#047857]">새 문제 {refillOutcome}개가 추가됐어요</div>
                  <div className="text-text-secondary">범위를 다시 골라 새 문제를 풀어보세요.</div>
                </div>
              </>
            ) : (
              <>
                <InfoIcon weight="fill" className="mt-0.5 shrink-0 text-lg text-text-tertiary" />
                <div className="flex-1">
                  {refillOutcome === "failed" ? (
                    <>
                      <div className="font-bold text-text-primary">문제 생성에 실패했어요</div>
                      <div className="text-text-secondary">잠시 후 다시 시도해 주세요.</div>
                    </>
                  ) : (
                    <>
                      <div className="font-bold text-text-primary">
                        이 자료에서 문제로 만들 만한 설명을 더 찾지 못했어요
                      </div>
                      <div className="text-text-secondary">
                        교재의 남은 내용이 문제 재료가 되기 어려웠어요. 다시
                        시도해도 결과가 비슷할 수 있어요.
                      </div>
                    </>
                  )}
                </div>
                {onRefill && (
                  <button
                    type="button"
                    onClick={onRefill}
                    className="shrink-0 self-center rounded-xl border border-border-primary bg-white px-4 py-2 text-[0.85rem] font-semibold text-text-secondary transition-colors hover:bg-bg-secondary"
                  >
                    다시 시도
                  </button>
                )}
              </>
            )}
          </div>
        )}

        {/* 풀 소진 → 리필 제안 — 생성은 분 단위 백그라운드 작업이라 접수만 하고
            "끝나면 문항 수에 반영"을 약속한다 (책장 "생성 중" 카드와 같은 세계관).
            직전 결과 배너가 떠 있으면(위) 거기 버튼이 있으니 이 카드는 접는다. */}
        {poolLow && onRefill && (refillState === "requested" || refillOutcome === null) && (
          <div className="mb-8 rounded-xl border border-accent/30 bg-accent/[0.04] p-5">
            {refillState === "idle" ? (
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex items-start gap-3">
                  <SparkleIcon weight="fill" className="mt-0.5 shrink-0 text-lg text-accent" />
                  <div className="text-[0.9rem] leading-relaxed">
                    <div className="font-bold text-text-primary">이 범위의 문제를 거의 다 풀었어요</div>
                    <div className="text-text-secondary">
                      교재에서 새 문제를 더 만들 수 있어요. 몇 분 걸리고, 끝나면
                      문항 수에 자동으로 더해져요.
                    </div>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={onRefill}
                  className="inline-flex shrink-0 items-center gap-2 rounded-xl bg-primary px-5 py-[0.6rem] text-[13.3333px] font-semibold leading-[normal] text-white shadow-sm transition-all hover:-translate-y-0.5 hover:bg-primary-hover hover:shadow-md"
                >
                  <SparkleIcon weight="fill" /> 새 문제 만들기
                </button>
              </div>
            ) : (
              <div className="flex items-start gap-3 text-[0.9rem] leading-relaxed">
                <CircleNotchIcon className="mt-0.5 shrink-0 animate-spin text-lg text-accent" />
                <div>
                  <div className="font-bold text-text-primary">새 문제를 만들고 있어요</div>
                  <div className="text-text-secondary">
                    몇 분 걸려요. 그동안 복습으로 다시 풀거나 다른 범위를 풀 수
                    있고, 완료되면 과목의 문항 수가 늘어나 있을 거예요.
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

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
