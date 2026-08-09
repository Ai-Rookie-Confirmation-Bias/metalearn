import { useState } from "react";
import { clsx } from "clsx";
import {
  CheckCircleIcon,
  XCircleIcon,
  LightbulbIcon,
  PaperclipIcon,
  ArrowRightIcon,
  ArrowCounterClockwiseIcon,
} from "@phosphor-icons/react";

import { submitAttempt } from "./api";
import type { AttemptResponse, SessionItem } from "./mock";

export type SolveResult = { tocIndex: number; correct: boolean };

const CIRCLED = (i: number) => String.fromCharCode(0x2460 + i); // ①②③④

// 정답 표시 문자열 (오답 배너 "정답은 ④" 부분)
function answerLabel(item: SessionItem, graded: AttemptResponse): string {
  const a = graded.answer;
  if (item.type === "mcq" && a.answerIndex !== undefined)
    return `${CIRCLED(a.answerIndex)} ${item.data.options?.[a.answerIndex] ?? ""}`;
  if (item.type === "trueFalse") return a.answer ? "O" : "X";
  if (item.type === "shortAnswer") return a.accepted?.[0] ?? "";
  if (item.type === "cloze") return (a.answers ?? []).map((b) => b.answer).join(", ");
  return "";
}

// 화면 2: 풀이·채점 — 확정안 §6-2. 한 문항씩, 서버 채점 후 💡 고른 선지 해설 + 📎 근거.
// recycled: items 뒤쪽 recycled개는 복습 재등장분 — 시작 안내 + 문항별 뱃지로 표시.
export function SolveView({
  items,
  recycled = 0,
  tocTitles,
  onSolved,
  onFinish,
}: {
  items: SessionItem[];
  recycled?: number;
  tocTitles: Record<number, string>;
  onSolved?: (item: SessionItem) => void;
  onFinish: (results: SolveResult[]) => void;
}) {
  const [index, setIndex] = useState(0);
  const [results, setResults] = useState<SolveResult[]>([]);
  const [graded, setGraded] = useState<AttemptResponse | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [picked, setPicked] = useState<number | boolean | null>(null); // mcq·OX 표시용

  const item = items[index];
  const isLast = index === items.length - 1;
  const isReview = index >= items.length - recycled; // 서버가 복습분을 뒤쪽에 붙여준다

  const submit = async (input: number | boolean | string | string[]) => {
    if (graded || submitting) return;
    setSubmitting(true);
    try {
      const resp = await submitAttempt(item.id, input); // 서버 채점 (정답은 서버만 앎)
      setGraded(resp);
      setResults((prev) => [...prev, { tocIndex: item.toc_index, correct: resp.correct }]);
      onSolved?.(item); // 풀이 기록 — 다음 세션의 "안 푼 문제 우선" 재료
    } finally {
      setSubmitting(false);
    }
  };

  const next = () => {
    if (isLast) {
      onFinish(results);
      return;
    }
    setIndex((i) => i + 1);
    setGraded(null);
    setPicked(null);
  };

  return (
    <div className="mx-auto w-full max-w-[720px] p-12">
      {/* 복습 안내 — 안 푼 문제가 부족했던 세션에만, 첫 문항에서 한 번 (한 화면 안내 하나) */}
      {recycled > 0 && index === 0 && !graded && (
        <div className="mb-4 flex items-start gap-3 rounded-xl bg-bg-secondary p-4 text-[0.85rem] leading-relaxed text-text-secondary">
          <ArrowCounterClockwiseIcon weight="bold" className="mt-0.5 shrink-0 text-base text-text-tertiary" />
          <span>
            안 푼 문제가 부족해서 <b className="text-text-primary">복습 {recycled}문항</b>이
            뒤쪽에 함께 나와요. 오래 전에 푼 것부터 다시 나옵니다.
          </span>
        </div>
      )}

      {/* 진행 헤더: 3/10 + 복습 뱃지 + 목차명 */}
      <div className="mb-4 flex items-center justify-between text-[0.9rem] font-semibold">
        <span className="flex items-center gap-2 text-text-primary">
          {index + 1}
          <span className="text-text-tertiary">/{items.length}</span>
          {isReview && (
            <span className="flex items-center gap-1 rounded-full bg-[#f59e0b]/10 px-2 py-0.5 text-xs font-semibold text-[#b45309]">
              <ArrowCounterClockwiseIcon weight="bold" /> 복습
            </span>
          )}
        </span>
        <span className="text-text-secondary">{tocTitles[item.toc_index]}</span>
      </div>
      <div className="mb-6 h-1.5 overflow-hidden rounded-full bg-border-primary">
        <div
          className="h-full rounded-full bg-accent transition-all duration-300"
          style={{ width: `${((index + (graded ? 1 : 0)) / items.length) * 100}%` }}
        />
      </div>

      {/* 문항 카드 */}
      <div className="rounded-2xl border border-border-primary bg-white p-8 shadow-sm">
        {/* key=item.id — 같은 유형이 연달아 나와도 문항마다 새로 마운트해
            입력 상태(단답 텍스트·빈칸 배열)를 초기화한다. 없으면 React가
            컴포넌트를 재사용해 이전 문항에 쓴 답이 그대로 남는다. */}
        {item.type === "mcq" && (
          <McqSolve key={item.id} item={item} graded={graded} picked={picked as number | null}
            onPick={(i) => { setPicked(i); void submit(i); }} />
        )}
        {item.type === "trueFalse" && (
          <TrueFalseSolve key={item.id} item={item} graded={graded} picked={picked as boolean | null}
            onPick={(v) => { setPicked(v); void submit(v); }} />
        )}
        {item.type === "shortAnswer" && (
          <ShortAnswerSolve key={item.id} item={item} graded={graded} onSubmit={(v) => void submit(v)} />
        )}
        {item.type === "cloze" && (
          <ClozeSolve key={item.id} item={item} graded={graded} onSubmit={(v) => void submit(v)} />
        )}
      </div>

      {/* 채점 결과 */}
      {graded && (
        <div className="mt-4 flex flex-col gap-3">
          {/* 정오 배너 */}
          <div
            className={clsx(
              "flex items-center gap-2 rounded-xl px-5 py-3.5 text-[0.95rem] font-semibold",
              graded.correct ? "bg-[#10b981]/10 text-[#047857]" : "bg-[#ef4444]/10 text-[#b91c1c]",
            )}
          >
            {graded.correct ? (
              <><CheckCircleIcon weight="fill" className="text-xl" /> 정답입니다</>
            ) : (
              <><XCircleIcon weight="fill" className="text-xl" /> 오답 — 정답은 {answerLabel(item, graded)}</>
            )}
          </div>

          {/* 💡 고른 선지 기준 해설 (오답 mcq) + 일반 해설 */}
          {(graded.explanation || graded.answer.explanation) && (
            <div className="flex items-start gap-3 rounded-xl bg-bg-secondary p-4 text-[0.9rem] leading-relaxed text-text-secondary">
              <LightbulbIcon weight="fill" className="mt-0.5 shrink-0 text-base text-[#f59e0b]" />
              <span>
                {graded.explanation && (
                  <>
                    {graded.explanation}
                    <br />
                  </>
                )}
                {graded.answer.explanation}
              </span>
            </div>
          )}

          {/* 📎 원문 근거 — 확정안 §4 시각 언어 (파란 테두리) */}
          <div className="rounded-xl border-2 border-accent/50 bg-accent/[0.03] p-5">
            <div className="mb-2 flex items-center gap-1.5 text-[0.85rem] font-bold text-accent">
              <PaperclipIcon weight="bold" /> 교재 {graded.evidence.pageFrom}쪽
            </div>
            <p className="text-[0.95rem] leading-relaxed text-text-primary">
              “{graded.evidence.text}”
            </p>
          </div>

          <button
            type="button"
            onClick={next}
            className="mt-2 inline-flex items-center justify-center gap-2 self-end rounded-xl bg-primary px-5 py-[0.6rem] text-[13.3333px] font-semibold leading-[normal] text-white shadow-sm transition-all hover:-translate-y-0.5 hover:bg-primary-hover hover:shadow-md"
          >
            {isLast ? "결과 보기" : "다음 문제"} <ArrowRightIcon />
          </button>
        </div>
      )}
    </div>
  );
}

// ── 유형별 입력 (기존 학습 블록과 같은 시각 문법 — 계약만 서버 채점) ──

function McqSolve({
  item, graded, picked, onPick,
}: {
  item: SessionItem;
  graded: AttemptResponse | null;
  picked: number | null;
  onPick: (i: number) => void;
}) {
  return (
    <div>
      <div className="mb-6 text-[1.1rem] font-semibold text-text-primary">{item.data.question}</div>
      <div className="flex flex-col gap-3">
        {(item.data.options ?? []).map((opt, i) => {
          const answerIndex = graded?.answer.answerIndex;
          const state = !graded
            ? picked === i ? "picked" : "idle"
            : i === answerIndex ? "correct"
            : picked === i ? "incorrect"
            : "idle";
          return (
            <button
              key={i}
              type="button"
              disabled={!!graded}
              onClick={() => onPick(i)}
              className={clsx(
                "flex items-center gap-4 rounded-xl border px-5 py-4 text-left text-[0.95rem] transition-all",
                state === "idle" &&
                  "border-border-primary bg-white text-text-primary enabled:hover:border-accent enabled:hover:bg-accent/[0.02]",
                state === "picked" && "border-accent bg-accent/[0.04] text-text-primary",
                state === "correct" && "border-[#10b981] bg-[#10b981]/10 font-semibold text-[#047857]",
                state === "incorrect" && "border-[#ef4444] bg-[#ef4444]/10 text-[#b91c1c]",
                graded && "cursor-default",
              )}
            >
              <span className="text-lg">{CIRCLED(i)}</span>
              {opt}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function TrueFalseSolve({
  item, graded, picked, onPick,
}: {
  item: SessionItem;
  graded: AttemptResponse | null;
  picked: boolean | null;
  onPick: (v: boolean) => void;
}) {
  return (
    <div>
      <div className="mb-6 text-[1.1rem] font-semibold text-text-primary">{item.data.statement}</div>
      <div className="flex gap-3">
        {([true, false] as const).map((v) => {
          const answer = graded?.answer.answer;
          const state = !graded
            ? "idle"
            : v === answer ? "correct"
            : picked === v ? "incorrect"
            : "idle";
          return (
            <button
              key={String(v)}
              type="button"
              disabled={!!graded}
              onClick={() => onPick(v)}
              className={clsx(
                "flex-1 rounded-xl border px-5 py-5 text-center text-2xl font-bold transition-all",
                state === "idle" &&
                  "border-border-primary bg-white text-text-primary enabled:hover:border-accent",
                state === "correct" && "border-[#10b981] bg-[#10b981]/10 text-[#047857]",
                state === "incorrect" && "border-[#ef4444] bg-[#ef4444]/10 text-[#b91c1c]",
              )}
            >
              {v ? "O" : "X"}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function ShortAnswerSolve({
  item, graded, onSubmit,
}: {
  item: SessionItem;
  graded: AttemptResponse | null;
  onSubmit: (v: string) => void;
}) {
  const [value, setValue] = useState("");
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        if (value.trim()) onSubmit(value.trim());
      }}
    >
      <div className="mb-6 text-[1.1rem] font-semibold text-text-primary">{item.data.prompt}</div>
      <div className="flex gap-3">
        <input
          type="text"
          value={value}
          disabled={!!graded}
          onChange={(e) => setValue(e.target.value)}
          placeholder="정답 입력"
          className={clsx(
            "flex-1 rounded-xl border px-5 py-3.5 text-[0.95rem] text-text-primary placeholder:text-text-tertiary focus:outline-none",
            !graded
              ? "border-border-primary focus:border-accent"
              : graded.correct
                ? "border-[#10b981] bg-[#10b981]/10 font-semibold text-[#047857]"
                : "border-[#ef4444] bg-[#ef4444]/10 text-[#b91c1c]",
          )}
        />
        {!graded && (
          <button
            type="submit"
            disabled={!value.trim()}
            className={clsx(
              "rounded-xl px-5 py-[0.6rem] text-[13.3333px] font-semibold leading-[normal] text-white transition-all",
              value.trim() ? "bg-primary hover:bg-primary-hover" : "cursor-not-allowed bg-text-tertiary opacity-70",
            )}
          >
            제출
          </button>
        )}
      </div>
    </form>
  );
}

function ClozeSolve({
  item, graded, onSubmit,
}: {
  item: SessionItem;
  graded: AttemptResponse | null;
  onSubmit: (v: string[]) => void;
}) {
  const blanks = (item.data.segments ?? []).filter((s) => s.kind === "blank").length;
  const [values, setValues] = useState<string[]>(Array(blanks).fill(""));
  const filled = values.every((v) => v.trim());

  let blankIdx = -1;
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        if (filled) onSubmit(values.map((v) => v.trim()));
      }}
    >
      <div className="mb-6 text-[1.05rem] leading-loose text-text-primary">
        {(item.data.segments ?? []).map((seg, i) => {
          if (seg.kind === "text") return <span key={i}>{seg.text}</span>;
          blankIdx += 1;
          const bi = blankIdx;
          return (
            <input
              key={i}
              type="text"
              value={values[bi] ?? ""}
              disabled={!!graded}
              onChange={(e) =>
                setValues((prev) => prev.map((v, j) => (j === bi ? e.target.value : v)))
              }
              className={clsx(
                "mx-1 inline-block w-36 rounded-lg border-b-2 border-t-0 border-x-0 bg-bg-secondary px-3 py-1 text-center text-[0.95rem] font-semibold focus:outline-none",
                !graded
                  ? "border-accent text-text-primary"
                  : graded.correct
                    ? "border-[#10b981] bg-[#10b981]/10 text-[#047857]"
                    : "border-[#ef4444] bg-[#ef4444]/10 text-[#b91c1c]",
              )}
            />
          );
        })}
      </div>
      {!graded && (
        <button
          type="submit"
          disabled={!filled}
          className={clsx(
            "rounded-xl px-5 py-[0.6rem] text-[13.3333px] font-semibold leading-[normal] text-white transition-all",
            filled ? "bg-primary hover:bg-primary-hover" : "cursor-not-allowed bg-text-tertiary opacity-70",
          )}
        >
          제출
        </button>
      )}
    </form>
  );
}
