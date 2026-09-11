import { useEffect, useMemo, useState } from "react";
import { clsx } from "clsx";

import { type RawDocument, type RawElement, fetchRaw } from "./api";
import { ControlText } from "./controlText";

/**
 * 1단계 원문 뷰어 — Document Parse가 뱉은 그대로를 자르지 않고 보여준다.
 *
 * 단계 결과의 표본 몇 개(앞 15개·160자)로는 파서가 실제로 어떻게 뱉었는지
 * 알 수 없다. 조각·개념 품질 문제가 여기서 시작되는 일이 많아서, 요소
 * 전체를 페이지 단위로 훑고 검색할 수 있어야 한다.
 *
 * 본문을 고정폭으로 그리고 제어문자를 배지로 바꾸는 건 취향이 아니다.
 * 실측: 이 PDF는 어절 사이가 U+0007(BEL)이라 그냥 그리면
 * "현대적인프로그래밍기술을"처럼 붙어 보인다 — 원인이 전혀 다른데
 * 증상이 같아 보이면 원문 뷰어를 만든 의미가 없다.
 */
export function RawViewer({ documentId }: { documentId: string }) {
  const [data, setData] = useState<RawDocument | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<"elements" | "markdown">("elements");
  const [page, setPage] = useState<number | "all">("all");
  const [query, setQuery] = useState("");

  useEffect(() => {
    let alive = true;
    setData(null);
    setError(null);
    fetchRaw(documentId)
      .then((next) => {
        if (!alive) return;
        setData(next);
        setPage(next.elements.find((e) => e.page !== null)?.page ?? "all");
      })
      .catch((e) => alive && setError(describe(e)));
    return () => {
      alive = false;
    };
  }, [documentId]);

  const pages = useMemo(() => {
    const set = new Set<number>();
    for (const el of data?.elements ?? []) if (el.page !== null) set.add(el.page);
    return [...set].sort((a, b) => a - b);
  }, [data]);

  // 검색 중에는 페이지 필터를 무시한다 — 어느 페이지에 있는지 모르니까 찾는다.
  const shown = useMemo(() => {
    const all = data?.elements ?? [];
    if (query.trim()) {
      const needle = query.trim().toLowerCase();
      return all.filter((el) => el.text.toLowerCase().includes(needle));
    }
    if (page === "all") return all;
    return all.filter((el) => el.page === page);
  }, [data, page, query]);

  if (error) {
    return (
      <Panel>
        <p className="text-sm text-red-700">원문을 불러오지 못했다 — {error}</p>
      </Panel>
    );
  }
  if (!data) {
    return (
      <Panel>
        <p className="text-sm text-text-tertiary">원문 불러오는 중…</p>
      </Panel>
    );
  }

  const capped = shown.slice(0, RENDER_CAP);

  return (
    <Panel>
      <div className="mb-1 flex flex-wrap items-center gap-2">
        <h3 className="mr-auto text-sm font-bold">
          정제 전 원본 (Document Parse 출력 그대로)
        </h3>
        <Tab active={tab === "elements"} onClick={() => setTab("elements")}>
          요소 {data.elements.length}개
        </Tab>
        <Tab active={tab === "markdown"} onClick={() => setTab("markdown")}>
          마크다운 {data.markdown.length.toLocaleString()}자
        </Tab>
      </div>

      {/* ␇가 보이는 게 어느 층의 이야기인지 헷갈리지 않게 명시한다.
          마크다운은 파서 출력을 그대로 보관하므로 2.5단계 정규화를 돌려도
          ␇가 남아 있고, 요소 배열은 실행한 단계까지 반영된다. */}
      <p className="mb-3 text-xs text-text-tertiary">
        마크다운은 파서 출력 그대로 보관한다 — 2.5단계 정규화를 돌려도 ␇가 그대로
        보인다. 요소 배열은 실행한 단계까지 반영된 상태다.
      </p>

      <QualityBar quality={data.quality} />

      {tab === "elements" ? (
        <>
          <div className="mb-3 flex flex-wrap items-center gap-2">
            <select
              value={String(page)}
              disabled={Boolean(query.trim())}
              onChange={(e) =>
                setPage(e.target.value === "all" ? "all" : Number(e.target.value))
              }
              className="rounded-lg border border-border-primary bg-white px-2.5 py-1.5 text-xs disabled:opacity-40"
            >
              <option value="all">전체 페이지</option>
              {pages.map((p) => (
                <option key={p} value={p}>
                  p.{p}
                </option>
              ))}
            </select>

            <div className="flex items-center gap-1">
              <button
                type="button"
                disabled={Boolean(query.trim()) || page === "all"}
                onClick={() => setPage((p) => movePage(pages, p, -1))}
                className="rounded-lg border border-border-primary px-2 py-1.5 text-xs disabled:opacity-40"
              >
                ←
              </button>
              <button
                type="button"
                disabled={Boolean(query.trim()) || page === "all"}
                onClick={() => setPage((p) => movePage(pages, p, 1))}
                className="rounded-lg border border-border-primary px-2 py-1.5 text-xs disabled:opacity-40"
              >
                →
              </button>
            </div>

            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="원문 검색 (페이지 무시하고 전체에서)"
              className="min-w-0 flex-1 rounded-lg border border-border-primary px-3 py-1.5 text-xs"
            />

            <span className="shrink-0 font-mono text-xs text-text-tertiary">
              {shown.length}개
              {shown.length > RENDER_CAP && ` (앞 ${RENDER_CAP}개만 표시)`}
            </span>
          </div>

          {capped.length === 0 ? (
            <p className="py-8 text-center text-xs text-text-tertiary">
              해당하는 요소가 없다.
            </p>
          ) : (
            <ul className="space-y-2">
              {capped.map((el) => (
                <ElementRow key={el.idx} element={el} query={query.trim()} />
              ))}
            </ul>
          )}
        </>
      ) : (
        <div>
          <button
            type="button"
            onClick={() => navigator.clipboard?.writeText(data.markdown)}
            className="mb-2 rounded-lg border border-border-primary px-2.5 py-1.5 text-xs text-text-secondary hover:bg-bg-secondary"
          >
            전문 복사
          </button>
          <pre className="max-h-[70vh] overflow-auto whitespace-pre-wrap break-words rounded-xl bg-bg-secondary p-3.5 font-mono text-xs leading-relaxed">
            {data.markdown || "(마크다운이 비어 있다)"}
          </pre>
        </div>
      )}
    </Panel>
  );
}

/** 한 번에 그릴 요소 수 상한. 전체 페이지 + 수천 요소면 브라우저가 버벅인다. */
const RENDER_CAP = 400;

/* ── 요소 한 줄 ──────────────────────────────────────────────── */

function ElementRow({ element, query }: { element: RawElement; query: string }) {
  return (
    <li
      className={clsx(
        "rounded-xl border p-3",
        element.removed
          ? "border-dashed border-border-primary bg-bg-secondary/60"
          : "border-border-primary",
      )}
    >
      <div className="mb-1.5 flex flex-wrap items-center gap-2 text-[11px]">
        <span className="font-mono font-bold text-text-tertiary">#{element.idx}</span>
        <span className="font-mono text-text-tertiary">p.{element.page ?? "?"}</span>
        <span className="rounded bg-gray-100 px-1.5 py-0.5 font-semibold text-gray-700">
          {element.category ?? "?"}
        </span>
        {element.has_image && (
          <span className="rounded bg-blue-50 px-1.5 py-0.5 font-semibold text-blue-700">
            base64 있음
          </span>
        )}
        {element.removed && (
          <span className="rounded bg-amber-50 px-1.5 py-0.5 font-semibold text-amber-800">
            removed: {element.removed}
          </span>
        )}
        <span className="ml-auto font-mono text-text-tertiary">
          {element.text.length}자
        </span>
      </div>
      {/* 원문 그대로 — 줄바꿈·공백을 하나도 건드리지 않는다.
          단, 안 보이는 제어문자만은 보이는 기호로 그린다(실측: 이 PDF는
          어절 사이가 U+0007이라 그냥 그리면 글자가 붙은 것처럼 보인다). */}
      <p className="whitespace-pre-wrap break-words font-mono text-xs leading-relaxed">
        {element.text ? (
          <ElementText text={element.text} query={query} />
        ) : (
          <span className="text-text-tertiary">(빈 요소)</span>
        )}
      </p>
    </li>
  );
}

/* ── 품질 진단 막대 ──────────────────────────────────────────── */

function QualityBar({ quality }: { quality: RawDocument["quality"] }) {
  const items: [string, string, boolean][] = [
    [
      "제어문자",
      quality.control_chars
        ? `${quality.control_chars.toLocaleString()}개 (${quality.control_names.join(", ")})`
        : "없음",
      quality.control_chars > 0,
    ],
    ["공백 비율", `${quality.space_ratio}%`, quality.space_ratio < 10],
    ["붙은 글자", `${quality.glued_ratio}%`, quality.glued_ratio > 5],
    // 판정에 안 쓰는 참고 수치라 빨간불을 켜지 않는다 (백엔드 주석 참고 —
    // 정상 한국어에서도 90%대가 나와 구분력이 없었다).
    ["끊긴 요소(참고)", `${quality.unterminated_ratio}%`, false],
    ["요소당 평균", `${quality.avg_chars.toLocaleString()}자`, false],
    ["총 문자", quality.chars.toLocaleString(), false],
  ];
  return (
    <div className="mb-3 rounded-xl bg-bg-secondary p-3">
      <div className="flex flex-wrap gap-x-5 gap-y-1.5">
        {items.map(([label, value, bad]) => (
          <div key={label} className="text-xs">
            <span className="text-text-tertiary">{label} </span>
            <span
              className={clsx(
                "font-mono font-bold",
                bad ? "text-red-600" : "text-text-primary",
              )}
            >
              {value}
            </span>
          </div>
        ))}
      </div>
      {quality.samples.length > 0 && (
        <div className="mt-2 border-t border-border-primary pt-2">
          <span className="text-[11px] text-text-tertiary">
            {quality.control_chars ? "제어문자가 섞인 구간 (␇ 자리)" : "공백이 사라진 구간"}{" "}
          </span>
          {quality.samples.map((s, i) => (
            <p key={i} className="break-all font-mono text-[11px] text-red-700">
              {s}
            </p>
          ))}
        </div>
      )}
    </div>
  );
}

/* ── 유틸 ────────────────────────────────────────────────────── */

function Panel({ children }: { children: React.ReactNode }) {
  return (
    <div className="rounded-2xl border border-border-primary bg-white p-5">
      {children}
    </div>
  );
}

function Tab({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={clsx(
        "rounded-lg px-3 py-1.5 text-xs font-semibold",
        active
          ? "bg-primary text-white"
          : "border border-border-primary text-text-secondary hover:bg-bg-secondary",
      )}
    >
      {children}
    </button>
  );
}

/**
 * 요소 본문 렌더러 — 제어문자를 보이는 배지로 바꾸고, 나머지에 검색어를 표시.
 *
 * 순서가 중요하다. 제어문자를 먼저 갈라내야 검색어 하이라이트가 그걸
 * 통과하지 못하고, 배지에 코드포인트를 찍을 수 있다.
 */
function ElementText({ text, query }: { text: string; query: string }) {
  return (
    <ControlText
      text={text}
      renderText={(part, i) => <Highlight key={i} text={part} query={query} />}
    />
  );
}

function Highlight({ text, query }: { text: string; query: string }) {
  if (!query) return <>{text}</>;
  const parts = text.split(new RegExp(`(${escapeRegExp(query)})`, "gi"));
  const needle = query.toLowerCase();
  return (
    <>
      {parts.map((part, i) =>
        part.toLowerCase() === needle ? (
          <mark key={i} className="rounded bg-amber-200 px-0.5">
            {part}
          </mark>
        ) : (
          <span key={i}>{part}</span>
        ),
      )}
    </>
  );
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function movePage(
  pages: number[],
  current: number | "all",
  delta: number,
): number | "all" {
  if (current === "all") return current;
  const index = pages.indexOf(current);
  if (index < 0) return current;
  return pages[Math.min(Math.max(index + delta, 0), pages.length - 1)];
}

function describe(error: unknown): string {
  const detail = (error as { response?: { data?: { detail?: string } } })?.response
    ?.data?.detail;
  return detail ?? (error as Error)?.message ?? String(error);
}
