import { clsx } from "clsx";

import { figureUrl } from "./api";
import { ControlText } from "./controlText";

type Row = Record<string, unknown>;

/**
 * 단계별 결과 표본 렌더러.
 *
 * 단계마다 봐야 할 게 다르다 — 그림은 이미지를 봐야 판정이 맞는지 알고,
 * 위치 복원은 앞뒤 문맥을 봐야 offset이 맞는지 안다. 그래서 일반 표로
 * 뭉뚱그리지 않고 필요한 것만 따로 그린다.
 */
export function StepPreview({
  step,
  rows,
  documentId,
}: {
  step: string;
  rows: Row[];
  documentId: string;
}) {
  if (step === "figures") return <FigureGrid rows={rows} documentId={documentId} />;
  if (step === "normalize") return <NormalizeDiff rows={rows} />;
  if (step === "locate_figures") return <LocateList rows={rows} />;
  if (step === "segment") return <SegmentList rows={rows} />;
  if (step === "topics") return <TopicList rows={rows} />;
  if (step === "extract") return <ConceptList rows={rows} />;
  if (step === "persist") return <MultiSegmentList rows={rows} />;
  if (step === "sentences") return <SentenceList rows={rows} />;
  return <GenericTable rows={rows} />;
}

/* ── 2. 그림 — 이미지를 직접 봐야 비전 판정이 맞는지 안다 ────── */

function FigureGrid({ rows, documentId }: { rows: Row[]; documentId: string }) {
  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-3">
      {rows.map((row, i) => (
        <figure
          key={i}
          className="overflow-hidden rounded-xl border border-border-primary"
        >
          <img
            src={figureUrl(documentId, String(row.figure_id))}
            alt=""
            className="h-36 w-full bg-bg-secondary object-contain"
          />
          <figcaption className="space-y-1 p-2.5 text-xs">
            <div className="flex items-center gap-1.5">
              <span className="font-mono text-text-tertiary">p.{String(row.page)}</span>
              <span className="rounded bg-gray-100 px-1.5 py-0.5 text-[10px] font-semibold">
                {String(row.category)}
              </span>
              <span
                className={clsx(
                  "rounded px-1.5 py-0.5 text-[10px] font-bold",
                  row.needs_vision
                    ? "bg-amber-100 text-amber-800"
                    : "bg-emerald-50 text-emerald-700",
                )}
              >
                {row.needs_vision ? "비전 필요" : "원문으로 충분"}
              </span>
            </div>
            <div className="text-text-tertiary">
              주변 원문 {String(row.context_len)}자
              {row.caption ? " · 캡션 있음" : " · 캡션 없음"}
            </div>
            <p className="line-clamp-2 leading-relaxed text-text-secondary">
              {String(row.context ?? "")}
            </p>
          </figcaption>
        </figure>
      ))}
    </div>
  );
}

/* ── 2-b. 위치 복원 — 앞뒤 문맥으로 offset이 맞는지 확인 ────── */

function LocateList({ rows }: { rows: Row[] }) {
  return (
    <ul className="space-y-2.5">
      {rows.map((row, i) => (
        <li key={i} className="rounded-xl bg-bg-secondary p-3 text-xs">
          <div className="mb-1.5 font-mono text-text-tertiary">
            요소 {String(row.element)} → 조각 #{String(row.segment)} · offset{" "}
            {String(row.offset)}
          </div>
          <p className="whitespace-pre-wrap break-all leading-relaxed">
            <span className="text-text-tertiary">…{String(row.before)}</span>
            <span className="mx-1 rounded bg-accent px-1.5 py-0.5 font-bold text-white">
              그림
            </span>
            <span className="text-text-tertiary">{String(row.after)}…</span>
          </p>
        </li>
      ))}
    </ul>
  );
}

/* ── 5. 조각 ─────────────────────────────────────────────────── */

function SegmentList({ rows }: { rows: Row[] }) {
  return (
    <ul className="space-y-2.5">
      {rows.map((row, i) => (
        <li key={i} className="rounded-xl border border-border-primary p-3">
          <div className="mb-1.5 flex flex-wrap items-center gap-2 text-xs">
            <span className="rounded bg-primary px-1.5 py-0.5 font-mono font-bold text-white">
              #{String(row.seq)}
            </span>
            <span className="font-semibold">{String(row.heading ?? "(제목 없음)")}</span>
            <span className="font-mono text-text-tertiary">
              {String(row.chars)}자 · p.{String(row.pages)} · el {String(row.elements)}
            </span>
          </div>
          <p className="line-clamp-3 whitespace-pre-wrap text-xs leading-relaxed text-text-secondary">
            {String(row.text)}
          </p>
        </li>
      ))}
    </ul>
  );
}

/* ── 2.5. 정규화 — before/after를 나란히 놓아야 치환이 맞는지 안다 ── */

function NormalizeDiff({ rows }: { rows: Row[] }) {
  const decorations = rows.filter((r) => r.kind === "decoration");
  const diffs = rows.filter((r) => r.kind !== "decoration");

  return (
    <div className="space-y-4">
      {decorations.length > 0 && (
        <div>
          <h4 className="mb-2 text-xs font-bold text-text-secondary">
            장식 판정 ({decorations.length}종) — 커버리지 = 등장 페이지 / 전체 페이지
          </h4>
          <ul className="space-y-1">
            {decorations.map((row, i) => (
              <li
                key={i}
                className="flex items-center gap-2 rounded-lg px-2 py-1.5 text-xs odd:bg-bg-secondary"
              >
                <span
                  className={clsx(
                    "shrink-0 rounded px-1.5 py-0.5 text-[10px] font-bold",
                    row.reason === "repeat"
                      ? "bg-red-50 text-red-700"
                      : "bg-amber-50 text-amber-800",
                  )}
                >
                  {row.reason === "repeat" ? "반복" : "러닝헤더"}
                </span>
                <span className="w-28 shrink-0 font-mono text-[11px] text-text-tertiary">
                  {String(row.hits)}회 · {String(row.coverage)}%
                </span>
                <span className="min-w-0 flex-1 truncate font-mono">
                  {String(row.text)}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {diffs.length > 0 && (
        <ul className="space-y-3">
          {diffs.map((row, i) => (
            <li
              key={i}
              className="overflow-hidden rounded-xl border border-border-primary"
            >
              <div className="flex items-center gap-2 border-b border-border-primary bg-bg-secondary px-3 py-1.5 text-[11px]">
                {row.idx !== undefined && (
                  <span className="font-mono text-text-tertiary">
                    #{String(row.idx)}
                  </span>
                )}
                <span className="rounded bg-gray-100 px-1.5 py-0.5 font-semibold">
                  {String(row.category)}
                </span>
                <span className="font-mono text-text-tertiary">
                  p.{String(row.page)}
                </span>
                <span className="ml-auto font-mono font-bold text-red-700">
                  {String(row.note)}
                </span>
              </div>

              <DiffRow label="before" text={String(row.before)} control />
              <DiffRow label="after" text={String(row.after)} />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function DiffRow({
  label,
  text,
  control = false,
}: {
  label: string;
  text: string;
  control?: boolean;
}) {
  return (
    <div className="flex gap-3 px-3 py-2 text-xs even:bg-bg-secondary/50">
      <span
        className={clsx(
          "w-14 shrink-0 font-mono text-[10px] font-bold",
          control ? "text-red-700" : "text-emerald-700",
        )}
      >
        {label}
      </span>
      {/* 원문을 건드리지 않고 그대로 그린다. before만 제어문자를 ␇ 배지로
          바꿔 어디에 있었는지 보여준다 — 1단계 원문 뷰어와 같은 렌더러다. */}
      <p className="min-w-0 flex-1 whitespace-pre-wrap break-words font-mono leading-relaxed">
        {control ? <ControlText text={text} /> : text}
      </p>
    </div>
  );
}

/* ── 5-b. 문장 ───────────────────────────────────────────────── */

function SentenceList({ rows }: { rows: Row[] }) {
  return (
    <ul className="space-y-1">
      {rows.map((row, i) => (
        <li key={i} className="flex gap-3 rounded-lg px-2 py-1.5 text-xs odd:bg-bg-secondary">
          <span className="w-24 shrink-0 font-mono text-text-tertiary">
            {String(row.range)}
          </span>
          <span className="min-w-0 flex-1 leading-relaxed">{String(row.text)}</span>
        </li>
      ))}
    </ul>
  );
}

/* ── 7. 목차 — 조각이 고르게 나뉘었는지가 핵심 ───────────────── */

function TopicList({ rows }: { rows: Row[] }) {
  const max = Math.max(...rows.map((r) => Number(r.count) || 0), 1);
  return (
    <ul className="space-y-2">
      {rows.map((row, i) => (
        <li key={i} className="rounded-xl border border-border-primary p-3">
          <div className="flex items-center gap-2 text-sm">
            <span className="font-mono text-xs text-text-tertiary">
              [{String(row.seq)}]
            </span>
            <span className="min-w-0 flex-1 truncate font-semibold">
              {String(row.title)}
            </span>
            <span className="shrink-0 font-mono text-xs text-text-secondary">
              조각 {String(row.count)}개
            </span>
          </div>
          <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-bg-secondary">
            <div
              className="h-full rounded-full bg-accent"
              style={{ width: `${((Number(row.count) || 0) / max) * 100}%` }}
            />
          </div>
          <div className="mt-1.5 font-mono text-[11px] text-text-tertiary">
            {(row.segments as number[])?.join(", ")}
          </div>
        </li>
      ))}
    </ul>
  );
}

/* ── 8. 개념 추출 ────────────────────────────────────────────── */

function ConceptList({ rows }: { rows: Row[] }) {
  return (
    <ul className="space-y-2">
      {rows.map((row, i) => (
        <li key={i} className="rounded-xl bg-bg-secondary p-3">
          <div className="flex items-baseline gap-2">
            <span className="text-sm font-semibold">{String(row.name)}</span>
            {row.key ? (
              <span className="font-mono text-[11px] text-text-tertiary">
                {String(row.key)}
              </span>
            ) : null}
          </div>
          <p className="mt-1 text-xs leading-relaxed text-text-secondary">
            {String(row.description)}
          </p>
          {(row.prerequisites as string[])?.length > 0 && (
            <div className="mt-1.5 flex flex-wrap gap-1">
              <span className="text-[11px] text-text-tertiary">선수</span>
              {(row.prerequisites as string[]).map((p) => (
                <span
                  key={p}
                  className="rounded bg-white px-1.5 py-0.5 text-[11px] text-text-secondary"
                >
                  {p}
                </span>
              ))}
            </div>
          )}
        </li>
      ))}
    </ul>
  );
}

/* ── 9+11. 다대다 증거 ───────────────────────────────────────── */

function MultiSegmentList({ rows }: { rows: Row[] }) {
  if (rows.length === 0) {
    return (
      <p className="text-xs text-text-tertiary">
        2개 이상 조각에 걸친 개념이 없다.
      </p>
    );
  }
  return (
    <ul className="space-y-1.5">
      {rows.map((row, i) => (
        <li
          key={i}
          className="flex items-center gap-3 rounded-lg px-2 py-1.5 text-xs odd:bg-bg-secondary"
        >
          <span className="min-w-0 flex-1 truncate font-semibold">
            {String(row.name)}
          </span>
          <span className="shrink-0 rounded bg-gray-100 px-1.5 py-0.5 text-[10px]">
            {String(row.source)}
          </span>
          <span className="shrink-0 font-mono text-text-secondary">
            조각 {(row.segments as number[])?.join(", ")}
          </span>
        </li>
      ))}
    </ul>
  );
}

/* ── 기본 표 ─────────────────────────────────────────────────── */

function GenericTable({ rows }: { rows: Row[] }) {
  const columns = Array.from(new Set(rows.flatMap((r) => Object.keys(r))));
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[500px] text-left text-xs">
        <thead>
          <tr className="border-b border-border-primary text-text-tertiary">
            {columns.map((c) => (
              <th key={c} className="whitespace-nowrap px-2 py-1.5 font-semibold">
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} className="border-b border-border-primary/60 align-top">
              {columns.map((c) => (
                <td key={c} className="px-2 py-1.5">
                  {row[c] === null || row[c] === undefined
                    ? "—"
                    : typeof row[c] === "boolean"
                      ? row[c]
                        ? "예"
                        : "아니오"
                      : String(row[c])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
