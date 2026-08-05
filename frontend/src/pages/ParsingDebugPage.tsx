import { useEffect, useRef, useState } from "react";
import { clsx } from "clsx";

import {
  type DebugState,
  type StepMeta,
  type StepResult,
  fetchState,
  fetchSteps,
  runStep,
  uploadDocument,
} from "@/features/parsing-debug/api";
import { RawViewer } from "@/features/parsing-debug/RawViewer";
import { StepPreview } from "@/features/parsing-debug/StepPreview";

/**
 * 파싱 파이프라인 단계별 실행기 (개발용).
 *
 * PDF를 넣고 단계 버튼을 하나씩 눌러 각 단계가 무엇을 하고 결과가 어떻게
 * 바뀌는지 확인한다. 운영 파이프라인과 같은 pipeline 함수를 호출하므로,
 * 여기서 본 결과가 곧 실제 동작이다.
 */
export function ParsingDebugPage() {
  const [steps, setSteps] = useState<StepMeta[]>([]);
  const [state, setState] = useState<DebugState | null>(null);
  const [results, setResults] = useState<Record<string, StepResult>>({});
  const [selected, setSelected] = useState<string | null>(null);
  const [running, setRunning] = useState<string | null>(null);
  // 단계를 다시 돌리면 원문 뷰어도 다시 받아야 한다 (문서 id는 그대로라
  // documentId만으로는 리마운트되지 않는다).
  const [runSeq, setRunSeq] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    fetchSteps().then(setSteps).catch((e) => setError(String(e)));
    // 새로고침해도 이어서 하도록 마지막 문서를 복원한다.
    const saved = localStorage.getItem("parsing-debug-doc");
    if (saved) {
      fetchState(saved)
        .then(setState)
        .catch(() => localStorage.removeItem("parsing-debug-doc"));
    }
  }, []);

  async function handleUpload(file: File) {
    setUploading(true);
    setError(null);
    setResults({});
    setSelected(null);
    try {
      const next = await uploadDocument(file);
      setState(next);
      localStorage.setItem("parsing-debug-doc", next.document_id);
    } catch (e) {
      setError(describe(e));
    } finally {
      setUploading(false);
    }
  }

  async function handleRun(step: string) {
    if (!state) return;
    setRunning(step);
    setError(null);
    try {
      const { result, state: next } = await runStep(state.document_id, step);
      setResults((prev) => ({ ...prev, [step]: result }));
      setState(next);
      setSelected(step);
      setRunSeq((n) => n + 1);
    } catch (e) {
      setError(describe(e));
    } finally {
      setRunning(null);
    }
  }

  const done = new Set(state?.done ?? []);
  const nextStep = steps.find((s) => !done.has(s.id))?.id ?? null;
  const shown = selected ? results[selected] : null;
  // 원문은 이번 세션에서 1단계를 안 돌렸어도(새로고침 후) 볼 수 있어야 한다.
  // 산출물이 DB에 남아 있으므로 done만 보면 된다.
  const showRaw = selected === "parse" && done.has("parse");

  return (
    <div className="min-h-screen bg-bg-secondary text-text-primary">
      <div className="mx-auto max-w-[1400px] px-6 py-8">
        <header className="mb-6">
          <h1 className="text-2xl font-bold">파싱 단계별 실행기</h1>
          <p className="mt-1 text-sm text-text-secondary">
            PDF를 올리고 위에서부터 한 단계씩 눌러 결과를 확인한다. 운영
            파이프라인과 같은 함수를 호출하므로 여기서 본 것이 실제 동작이다.
          </p>
        </header>

        <UploadBar
          state={state}
          uploading={uploading}
          fileRef={fileRef}
          onUpload={handleUpload}
          onReset={() => {
            localStorage.removeItem("parsing-debug-doc");
            setState(null);
            setResults({});
            setSelected(null);
          }}
        />

        {error && (
          <div className="mb-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
            <span className="font-semibold">실패 </span>
            <span className="break-all">{error}</span>
          </div>
        )}

        {state && <Counters state={state} />}

        <div className="grid grid-cols-1 gap-5 lg:grid-cols-[380px_1fr]">
          <ol className="space-y-2">
            {steps.map((step, i) => (
              <StepRow
                key={step.id}
                index={i}
                step={step}
                done={done.has(step.id)}
                isNext={step.id === nextStep}
                isSelected={selected === step.id}
                running={running === step.id}
                disabled={!state || running !== null}
                result={results[step.id]}
                selectable={
                  Boolean(results[step.id]) ||
                  (step.id === "parse" && done.has("parse"))
                }
                onRun={() => handleRun(step.id)}
                onSelect={() => setSelected(step.id)}
              />
            ))}
          </ol>

          <section className="min-w-0 space-y-4">
            {shown && <ResultPanel result={shown} documentId={state!.document_id} />}
            {showRaw && (
              <RawViewer key={runSeq} documentId={state!.document_id} />
            )}
            {!shown && !showRaw && <EmptyPanel hasDocument={Boolean(state)} />}
          </section>
        </div>
      </div>
    </div>
  );
}

/* ── 상단 업로드 ─────────────────────────────────────────────── */

function UploadBar({
  state,
  uploading,
  fileRef,
  onUpload,
  onReset,
}: {
  state: DebugState | null;
  uploading: boolean;
  fileRef: React.RefObject<HTMLInputElement | null>;
  onUpload: (file: File) => void;
  onReset: () => void;
}) {
  return (
    <div className="mb-4 flex flex-wrap items-center gap-3 rounded-2xl border border-border-primary bg-white p-4">
      <input
        ref={fileRef}
        type="file"
        accept=".pdf,.png,.jpg,.jpeg"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) onUpload(file);
          e.target.value = "";
        }}
      />
      <button
        type="button"
        disabled={uploading}
        onClick={() => fileRef.current?.click()}
        className="rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-white hover:bg-primary-hover disabled:opacity-50"
      >
        {uploading ? "업로드 중…" : "PDF 선택"}
      </button>

      {state ? (
        <>
          <div className="min-w-0 flex-1">
            <div className="truncate text-sm font-semibold">{state.filename}</div>
            <div className="font-mono text-xs text-text-tertiary">
              {state.document_id}
            </div>
          </div>
          <span className="rounded-lg bg-bg-secondary px-2.5 py-1 text-xs font-semibold text-text-secondary">
            {state.status}
          </span>
          {state.density_grade && (
            <span
              className={clsx(
                "rounded-lg px-2.5 py-1 text-xs font-semibold",
                state.density_grade === "full"
                  ? "bg-emerald-50 text-emerald-700"
                  : "bg-amber-50 text-amber-700",
              )}
            >
              {state.density_grade === "full" ? "본문 가능" : "뼈대만"}
            </span>
          )}
          <button
            type="button"
            onClick={onReset}
            className="rounded-xl border border-border-primary px-3 py-2 text-sm text-text-secondary hover:bg-bg-secondary"
          >
            초기화
          </button>
        </>
      ) : (
        <span className="text-sm text-text-tertiary">
          같은 파일을 다시 올리면 이전 산출물을 지우고 처음부터 시작한다.
        </span>
      )}
    </div>
  );
}

/* ── 산출물 카운터 ───────────────────────────────────────────── */

function Counters({ state }: { state: DebugState }) {
  const items: [string, number | string][] = [
    ["요소", state.counts.elements],
    ["그림", `${state.counts.figures_located}/${state.counts.figures}`],
    ["조각", state.counts.segments],
    ["문장", state.counts.sentences],
    ["목차", state.counts.topics],
    ["개념", state.counts.concepts],
    ["선후관계", state.counts.edges],
  ];
  return (
    <div className="mb-5 grid grid-cols-4 gap-2 sm:grid-cols-7">
      {items.map(([label, value]) => (
        <div
          key={label}
          className="rounded-xl border border-border-primary bg-white px-3 py-2.5 text-center"
        >
          <div className="text-lg font-bold tabular-nums">{value}</div>
          <div className="text-xs text-text-tertiary">{label}</div>
        </div>
      ))}
    </div>
  );
}

/* ── 단계 한 줄 ──────────────────────────────────────────────── */

function StepRow({
  index,
  step,
  done,
  isNext,
  isSelected,
  running,
  disabled,
  result,
  selectable,
  onRun,
  onSelect,
}: {
  index: number;
  step: StepMeta;
  done: boolean;
  isNext: boolean;
  isSelected: boolean;
  running: boolean;
  disabled: boolean;
  result?: StepResult;
  selectable: boolean;
  onRun: () => void;
  onSelect: () => void;
}) {
  return (
    <li
      onClick={() => selectable && onSelect()}
      className={clsx(
        "rounded-2xl border bg-white p-3.5 transition-colors",
        isSelected
          ? "border-accent ring-1 ring-accent"
          : isNext
            ? "border-accent/40"
            : "border-border-primary",
        selectable && "cursor-pointer hover:bg-bg-secondary",
      )}
    >
      <div className="flex items-start gap-3">
        <span
          className={clsx(
            "mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-bold",
            done
              ? "bg-emerald-500 text-white"
              : isNext
                ? "bg-accent text-white"
                : "bg-bg-secondary text-text-tertiary",
          )}
        >
          {done ? "✓" : index + 1}
        </span>

        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="truncate text-sm font-semibold">{step.label}</span>
            <span
              className={clsx(
                "shrink-0 rounded px-1.5 py-0.5 text-[10px] font-bold",
                step.kind === "호출"
                  ? "bg-blue-50 text-blue-700"
                  : "bg-gray-100 text-gray-600",
              )}
            >
              {step.kind}
            </span>
          </div>
          <p className="mt-1 text-xs leading-relaxed text-text-secondary">
            {step.desc}
          </p>
          {result && (
            <p className="mt-1.5 font-mono text-[11px] text-text-tertiary">
              {result.elapsed_ms.toLocaleString()}ms · Solar {result.solar_calls}회
            </p>
          )}
        </div>

        <button
          type="button"
          disabled={disabled || running}
          onClick={(e) => {
            e.stopPropagation();
            onRun();
          }}
          className={clsx(
            "shrink-0 rounded-lg px-3 py-1.5 text-xs font-semibold",
            done
              ? "border border-border-primary text-text-secondary hover:bg-bg-secondary"
              : "bg-primary text-white hover:bg-primary-hover",
            (disabled || running) && "opacity-40",
          )}
        >
          {running ? "실행 중…" : done ? "다시" : "실행"}
        </button>
      </div>
    </li>
  );
}

/* ── 결과 패널 ───────────────────────────────────────────────── */

function ResultPanel({
  result,
  documentId,
}: {
  result: StepResult;
  documentId: string;
}) {
  return (
    <div className="space-y-4">
      <div className="rounded-2xl border border-border-primary bg-white p-5">
        <div className="mb-3 flex items-baseline justify-between gap-3">
          <h2 className="text-lg font-bold">{result.label}</h2>
          <span className="shrink-0 font-mono text-xs text-text-tertiary">
            {result.elapsed_ms.toLocaleString()}ms · Solar {result.solar_calls}회
          </span>
        </div>

        <dl className="divide-y divide-border-primary">
          {Object.entries(result.summary).map(([key, value]) => (
            <div key={key} className="flex gap-4 py-2">
              <dt className="w-40 shrink-0 text-sm text-text-secondary">{key}</dt>
              <dd className="min-w-0 flex-1 break-words font-mono text-sm">
                {formatValue(value)}
              </dd>
            </div>
          ))}
        </dl>

        {result.note && (
          <p className="mt-4 rounded-xl bg-bg-secondary px-3.5 py-3 text-xs leading-relaxed text-text-secondary">
            {result.note}
          </p>
        )}
      </div>

      {result.preview.length > 0 && (
        <div className="rounded-2xl border border-border-primary bg-white p-5">
          <h3 className="mb-3 text-sm font-bold text-text-secondary">
            결과 표본 ({result.preview.length}개)
          </h3>
          <StepPreview
            step={result.step}
            rows={result.preview}
            documentId={documentId}
          />
        </div>
      )}
    </div>
  );
}

function EmptyPanel({ hasDocument }: { hasDocument: boolean }) {
  return (
    <div className="flex h-64 items-center justify-center rounded-2xl border border-dashed border-border-primary bg-white text-sm text-text-tertiary">
      {hasDocument
        ? "왼쪽에서 단계를 실행하면 결과가 여기 나온다."
        : "PDF를 먼저 올린다."}
    </div>
  );
}

/* ── 유틸 ────────────────────────────────────────────────────── */

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (Array.isArray(value)) return value.length ? value.join(", ") : "없음";
  if (typeof value === "object") {
    return Object.entries(value as Record<string, unknown>)
      .map(([k, v]) => `${k} ${v}`)
      .join(" · ");
  }
  return String(value);
}

function describe(error: unknown): string {
  const detail = (error as { response?: { data?: { detail?: string } } })?.response
    ?.data?.detail;
  if (detail) return detail;
  return (error as Error)?.message ?? String(error);
}
