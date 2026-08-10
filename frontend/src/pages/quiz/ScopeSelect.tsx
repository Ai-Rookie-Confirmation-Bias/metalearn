import { useState } from "react";
import { clsx } from "clsx";
import {
  ArrowLeftIcon,
  BookOpenIcon,
  CheckSquareIcon,
  SquareIcon,
  LightningIcon,
  PlayIcon,
} from "@phosphor-icons/react";

import type { QuizBankSummary } from "./mock";

const COUNT_PRESETS = [10, 20, 30] as const;

// 화면 1: 범위 선택 — 확정안 §6-1. 목차 체크박스 + 문항 수, ⚡ 격리 안내 고정 문구.
// solvedByToc: 이 브라우저의 풀이 기록(localStorage) 목차별 집계 — "안 푼 N"
// 표시용. 풀이 기록이 있는 목차만 표기가 달라진다.
export function ScopeSelect({
  title,
  summary,
  solvedByToc = {},
  refilling = false,
  refillOutcome = null,
  onStart,
  onBack,
}: {
  title: string;
  summary: QuizBankSummary;
  solvedByToc?: Record<number, number>;
  refilling?: boolean; // 리필 배치 진행 중 — 풀이는 그대로 가능, 안내만
  // 직전 리필 결과 — 추가된 문항 수(0=빈손) 또는 "failed". 진행 중이 우선.
  refillOutcome?: number | "failed" | null;
  onStart: (tocIndexes: number[], count: number) => void;
  onBack: () => void;
}) {
  const [checked, setChecked] = useState<Set<number>>(new Set());
  // 문항 수: 프리셋(10/20/30) 또는 직접 입력. 은행 계획(형태별 유형 배분)은 생성
  // 시점 일이라 몇 개를 뽑든 충돌 없음 — 서빙은 범위 내 샘플링일 뿐.
  const [countMode, setCountMode] = useState<number | "custom">(10);
  const [customCount, setCustomCount] = useState("15");

  const toggle = (i: number) =>
    setChecked((prev) => {
      const next = new Set(prev);
      if (next.has(i)) next.delete(i);
      else next.add(i);
      return next;
    });

  const selectedCount = summary.tocs
    .filter((t) => checked.has(t.toc_index))
    .reduce((n, t) => n + t.item_count, 0);

  const requested =
    countMode === "custom" ? Number.parseInt(customCount, 10) || 0 : countMode;
  // 범위에 있는 것보다 많이 요청하면 있는 만큼으로 — 버튼 라벨이 실제 개수를 보여준다
  const sessionCount = Math.min(requested, selectedCount);
  const canStart = checked.size > 0 && sessionCount > 0;

  return (
    <div className="mx-auto w-full max-w-[720px] p-12">
      <button
        type="button"
        onClick={onBack}
        className="mb-4 flex items-center gap-2 text-[0.9rem] font-semibold text-text-secondary transition-colors hover:text-primary"
      >
        <ArrowLeftIcon /> 다른 과목
      </button>

      <div className="rounded-2xl border border-border-primary bg-white p-8 shadow-sm">
        <div className="mb-6 flex items-center justify-between">
          {/* "기출 스타일" 뱃지를 여기 달지 않는다 — 기출 자료가 있다는 것과
              은행이 기출풍이라는 것은 다른 말이라, 상단에 붙이면 문제집 전체가
              기출 스타일인 줄 알게 된다 (실사용 혼동 실측). 기출 관련 표시는
              아래 카드(생성 버튼/기출만 토글)가 전담한다. */}
          <h2 className="flex items-center gap-2 text-xl font-bold text-primary">
            📝 {title} — 문제은행
          </h2>
          <span className="text-[0.9rem] font-semibold text-text-secondary">
            총 {summary.total}문항
          </span>
        </div>

        {/* 리필 진행 안내 — 완료되면 폴링이 총 문항 수를 갱신한다.
            완료 후엔 같은 자리에서 결과(추가됨/빈손/실패)로 이어진다. */}
        {refilling ? (
          <div className="mb-6 flex items-center gap-2 rounded-lg bg-accent/[0.06] px-4 py-2.5 text-[0.85rem] font-semibold text-accent">
            <span className="h-3.5 w-3.5 shrink-0 animate-spin rounded-full border-2 border-accent/30 border-t-accent" />
            새 문제를 만들고 있어요 — 완료되면 문항 수에 더해져요. 지금도 풀 수 있어요.
          </div>
        ) : typeof refillOutcome === "number" && refillOutcome > 0 ? (
          <div className="mb-6 rounded-lg bg-[#10b981]/[0.08] px-4 py-2.5 text-[0.85rem] font-semibold text-[#047857]">
            ✓ 새 문제 {refillOutcome}개가 추가됐어요 — 범위를 골라 풀어보세요.
          </div>
        ) : refillOutcome !== null ? (
          <div className="mb-6 rounded-lg bg-bg-secondary px-4 py-2.5 text-[0.85rem] text-text-secondary">
            {refillOutcome === "failed"
              ? "문제 생성에 실패했어요 — 잠시 후 다시 시도해 주세요."
              : "이 자료에서 문제로 만들 만한 설명을 더 찾지 못했어요 — 다시 시도해도 결과가 비슷할 수 있어요."}
          </div>
        ) : null}

        <div className="mb-2 text-[0.85rem] font-bold text-text-tertiary">범위</div>
        <div className="mb-6 flex flex-col gap-2">
          {summary.tocs.map((toc) => {
            const on = checked.has(toc.toc_index);
            return (
              <button
                key={toc.toc_index}
                type="button"
                onClick={() => toggle(toc.toc_index)}
                className={clsx(
                  "flex items-center justify-between rounded-xl border px-5 py-4 text-left transition-all",
                  on
                    ? "border-accent bg-accent/[0.04]"
                    : "border-border-primary bg-white hover:border-accent/50",
                )}
              >
                <span className="flex min-w-0 items-center gap-3">
                  {on ? (
                    <CheckSquareIcon weight="fill" className="shrink-0 text-xl text-accent" />
                  ) : (
                    <SquareIcon className="shrink-0 text-xl text-text-tertiary" />
                  )}
                  <span
                    className={clsx(
                      "truncate text-[0.95rem]",
                      on ? "font-semibold text-text-primary" : "text-text-secondary",
                    )}
                  >
                    {toc.title}
                  </span>
                  {/* 학습 페이지에서 배운 목차 표시 — 안내용일 뿐 문항은 동일 */}
                  {toc.studied && (
                    <span className="flex shrink-0 items-center gap-1 rounded-full bg-[#10b981]/10 px-2 py-0.5 text-xs font-semibold text-[#047857]">
                      <BookOpenIcon weight="fill" /> 학습함
                    </span>
                  )}
                </span>
                {/* 풀이 기록이 있으면 "안 푼 N"을 함께 — 어디를 풀지 고르는
                    화면이라 남은 양이 곧 판단 재료다. 재파싱으로 문항이 줄어
                    기록이 더 많아질 수 있으니 0 밑으로는 안 내려간다. */}
                {(() => {
                  const fresh = Math.max(
                    0,
                    toc.item_count - (solvedByToc[toc.toc_index] ?? 0),
                  );
                  const hasSolved = (solvedByToc[toc.toc_index] ?? 0) > 0;
                  return (
                    <span className="shrink-0 text-[0.85rem] text-text-tertiary">
                      {hasSolved && fresh > 0 && (
                        <b className="font-semibold text-accent">안 푼 {fresh}</b>
                      )}
                      {hasSolved && fresh === 0 && (
                        <b className="font-semibold text-[#047857]">모두 풀어봄</b>
                      )}
                      {hasSolved && " · "}
                      {toc.item_count}문항
                    </span>
                  );
                })()}
              </button>
            );
          })}
        </div>

        <div className="mb-2 text-[0.85rem] font-bold text-text-tertiary">문항 수</div>
        <div className="mb-6 flex flex-wrap items-center gap-2">
          {COUNT_PRESETS.map((n) => (
            <button
              key={n}
              type="button"
              onClick={() => setCountMode(n)}
              className={clsx(
                "rounded-xl border px-4 py-2 text-[0.9rem] transition-all",
                countMode === n
                  ? "border-accent bg-accent/[0.04] font-semibold text-text-primary"
                  : "border-border-primary text-text-secondary hover:border-accent/50",
              )}
            >
              {n}문항
            </button>
          ))}
          <button
            type="button"
            onClick={() => setCountMode("custom")}
            className={clsx(
              "rounded-xl border px-4 py-2 text-[0.9rem] transition-all",
              countMode === "custom"
                ? "border-accent bg-accent/[0.04] font-semibold text-text-primary"
                : "border-border-primary text-text-secondary hover:border-accent/50",
            )}
          >
            직접 입력
          </button>
          {countMode === "custom" && (
            <input
              type="number"
              min={1}
              value={customCount}
              onChange={(e) => setCustomCount(e.target.value)}
              className="w-20 rounded-xl border border-border-primary px-3 py-2 text-center text-[0.9rem] text-text-primary outline-none transition-colors focus:border-accent"
              aria-label="문항 수 직접 입력"
            />
          )}
          {checked.size > 0 && requested > selectedCount && (
            <span className="text-[0.8rem] text-text-tertiary">
              선택한 범위엔 {selectedCount}문항뿐이라 {selectedCount}개로 시작해요
            </span>
          )}
        </div>

        <div className="flex items-center justify-between border-t border-border-primary pt-6">
          <span className="text-[0.9rem] text-text-secondary">
            선택: <b className="text-text-primary">{selectedCount}문항</b>
          </span>
          <button
            type="button"
            disabled={!canStart}
            onClick={() => onStart([...checked], sessionCount)}
            className={clsx(
              "inline-flex items-center gap-2 rounded-xl px-5 py-[0.6rem] text-[13.3333px] font-semibold leading-[normal] text-white shadow-sm transition-all",
              canStart
                ? "bg-primary hover:-translate-y-0.5 hover:bg-primary-hover hover:shadow-md"
                : "cursor-not-allowed bg-text-tertiary opacity-70",
            )}
          >
            <PlayIcon weight="fill" /> {canStart ? `${sessionCount}문항 풀기` : "문항 풀기"}
          </button>
        </div>
      </div>

      {/* ⚡ 안내 — 확정안 §4 시각 언어 (회색 배경, 한 화면에 하나) */}
      <div className="mt-4 flex items-start gap-3 rounded-xl bg-bg-secondary p-4 text-[0.85rem] leading-relaxed text-text-secondary">
        <LightningIcon weight="fill" className="mt-0.5 shrink-0 text-base text-text-tertiary" />
        <span>
          문제는 학습 기록과 무관하게 모든 사용자에게 같습니다.
          <br />
          학습 기록은 추천과 <b>학습함</b> 표시에만 쓰여요.
        </span>
      </div>
    </div>
  );
}
