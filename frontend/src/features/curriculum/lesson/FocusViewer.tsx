// 몰입 학습 모드 — 2D 매트릭스 뷰어 (X = 화면, Y = 개념).
//
// `feat/yoonhs-integration`의 FocusViewer를 커리큘럼 스택으로 옮긴 것이다.
// 격자·줌팬 연출·키보드·미니맵·스크롤 스냅은 그대로고, **셀의 단위가 다르다**:
//
//     원본   Y = 블록 하나 (설명 / 빈칸 / 객관식 …)
//     여기   Y = **개념 하나** ([설명 · 그림 · 그 개념 빈칸])
//
// 개념 단위로 바꾼 이유는 일반 학습 화면이 이미 그렇게 묶여 있기 때문이다
// (`splitLesson`). 두 화면이 같은 규칙을 써야 몰입 모드에서만 순서가 다르거나
// 그림이 빠지는 일이 안 생긴다. 셀 수도 줄어 한 절이 서너 칸에 들어온다.
//
// 스크롤·연출에서 원본이 이미 해결해 둔 것을 그대로 지킨다:
//   · 프로그램 스크롤 중에는 수동 동기화를 막는다(둘이 y를 서로 되돌린다)
//   · 잠긴 화면으로는 못 넘어간다
//   · 빈칸에 타이핑 중이면 키보드 이동을 무시한다
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowLeftIcon,
  ArrowRightIcon,
  ArrowUpIcon,
  ArrowDownIcon,
  CheckCircleIcon,
  MapTrifoldIcon,
} from "@phosphor-icons/react";
import { clsx } from "clsx";

import type { ChapterOut, SectionOut } from "@/features/curriculum/api/curriculum";
import type { LessonParts } from "@/features/curriculum/lesson/steps";

import "./focus.css";

// 원본 목업의 renderMatrix 타이밍. 줌아웃 → 슬라이드 → 줌인 → 안착.
const ZOOM_PAN_MS = 400;
const ZOOM_IN_MS = 500;
const SETTLE_MS = 600;

export type FocusColumn = {
  section: SectionOut;
  chapter: ChapterOut;
  /** 미니맵 라벨 "장.절". */
  label: string;
};

/** 목차들을 평탄화해 X축 컬럼으로. 목차 순서 = 학습 순서 그대로. */
export function toColumns(chapters: ChapterOut[]): FocusColumn[] {
  return chapters.flatMap((c) =>
    c.sections.map((s, si) => ({
      section: s,
      chapter: c,
      label: `${c.index + 1}.${si + 1}`,
    })),
  );
}

export function FocusViewer({
  columns,
  currentSectionId,
  onNavigate,
  parts,
  loading,
  renderStep,
  renderTail,
  onExit,
}: {
  columns: FocusColumn[];
  currentSectionId: string;
  onNavigate: (sectionId: string) => void;
  parts: LessonParts | null;
  loading: boolean;
  /** 개념 덩이 하나를 그린다. 일반 화면과 같은 컴포넌트를 넘겨 받는다. */
  renderStep: (index: number) => React.ReactNode;
  /** 마지막 셀(객관식·원문). 없으면 null. */
  renderTail: () => React.ReactNode;
  onExit: () => void;
}) {
  const x = Math.max(
    0,
    columns.findIndex((c) => c.section.sectionId === currentSectionId),
  );
  const [y, setY] = useState(0);
  const [zoomedOut, setZoomedOut] = useState(false);
  const [minimapOpen, setMinimapOpen] = useState(false);
  const animatingRef = useRef(false);
  const columnRefs = useRef<(HTMLDivElement | null)[]>([]);

  const steps = parts?.steps ?? [];
  const hasTail = Boolean(parts?.mcq);
  // 로딩 중엔 상태 카드 한 장. 아니면 개념 덩이들 + 꼬리 한 칸.
  const cellCount = loading || !steps.length ? 1 : steps.length + (hasTail ? 1 : 0);

  const scrollToCell = useCallback(
    (targetY: number, smooth: boolean) => {
      const col = columnRefs.current[x];
      if (!col) return;
      const cell = col.querySelectorAll<HTMLElement>(".matrix-block")[targetY];
      cell?.scrollIntoView({ behavior: smooth ? "smooth" : "auto", block: "center" });
    },
    [x],
  );

  // Y 변경 → 그 셀을 정중앙으로. 프로그램 스크롤 중에는 수동 동기화를 막는다.
  const programmaticRef = useRef(false);
  useEffect(() => {
    programmaticRef.current = true;
    scrollToCell(y, true);
    const t = window.setTimeout(() => {
      programmaticRef.current = false;
    }, 800);
    return () => window.clearTimeout(t);
  }, [y, scrollToCell]);

  // 화면을 옮기거나 내용이 도착하면 첫 칸부터.
  useEffect(() => {
    setY(0);
    const raf = requestAnimationFrame(() => scrollToCell(0, false));
    return () => cancelAnimationFrame(raf);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentSectionId, loading, steps.length]);

  // 손수 스크롤 ↔ y 동기화. 멈춘 뒤에 중앙에 가장 가까운 칸을 활성으로 —
  // 즉시 갱신하면 프로그램 스크롤과 서로를 되돌린다.
  const syncTimer = useRef<number | null>(null);
  const onColumnScroll = () => {
    if (animatingRef.current || programmaticRef.current) return;
    if (syncTimer.current) window.clearTimeout(syncTimer.current);
    syncTimer.current = window.setTimeout(() => {
      const col = columnRefs.current[x];
      if (!col) return;
      const center = col.scrollTop + col.clientHeight / 2;
      let best = 0;
      let bestDist = Infinity;
      col.querySelectorAll<HTMLElement>(".matrix-block").forEach((cell, i) => {
        const d = Math.abs(cell.offsetTop + cell.offsetHeight / 2 - center);
        if (d < bestDist) {
          bestDist = d;
          best = i;
        }
      });
      setY((cur) => (best !== cur ? best : cur));
    }, 120);
  };

  const moveY = (delta: number) => {
    if (animatingRef.current) return;
    const next = y + delta;
    if (next >= 0 && next < cellCount) setY(next);
  };

  // 가로 이동 — 줌아웃 → 옮김 → 줌인. 잠긴 화면으로는 안 간다.
  const canEnter = (i: number) => i >= 0 && i < columns.length;

  const goTo = (i: number) => {
    if (animatingRef.current || i === x || !canEnter(i)) return;
    setMinimapOpen(false);
    animatingRef.current = true;
    setZoomedOut(true);
    window.setTimeout(() => {
      onNavigate(columns[i].section.sectionId);
      window.setTimeout(() => {
        setZoomedOut(false);
        window.setTimeout(() => {
          animatingRef.current = false;
        }, SETTLE_MS);
      }, ZOOM_IN_MS);
    }, ZOOM_PAN_MS);
  };

  // 키보드. **입력 중이면 무시한다** — 빈칸에 답을 타이핑하다 화면이 넘어가면
  // 쓰던 답을 잃는다.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement;
      if (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.isContentEditable) return;
      if (e.key === "Escape") return onExit();
      if (e.key === "ArrowUp") {
        e.preventDefault();
        moveY(-1);
      } else if (e.key === "ArrowDown") {
        e.preventDefault();
        moveY(1);
      } else if (e.key === "ArrowLeft") {
        e.preventDefault();
        goTo(x - 1);
      } else if (e.key === "ArrowRight") {
        e.preventDefault();
        goTo(x + 1);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  const here = columns[x];
  const cells = useMemo(
    () => Array.from({ length: cellCount }, (_, i) => i),
    [cellCount],
  );

  return (
    <div className="focus-root">
      <div className="focus-top-bar">
        <button type="button" className="focus-exit" onClick={onExit}>
          ← 나가기 (ESC)
        </button>
        <span className="focus-chapter-title-inline">
          {here ? `${here.chapter.title} · ${here.section.title}` : ""}
        </span>
        <button
          type="button"
          className="minimap-toggle"
          onClick={() => setMinimapOpen((v) => !v)}
          aria-label="전체 보기"
        >
          <MapTrifoldIcon />
        </button>
      </div>

      <div className="matrix-viewport">
        <div className={clsx("matrix-map", zoomedOut && "zoomed-out")}>
          <div
            className="matrix-x-track"
            style={{ transform: `translateX(-${x * 100}vw)` }}
          >
            {columns.map((col, ci) => (
              <div
                key={col.section.sectionId}
                ref={(el) => {
                  columnRefs.current[ci] = el;
                }}
                className="matrix-chapter"
                onScroll={ci === x ? onColumnScroll : undefined}
              >
                <div className="matrix-y-track">
                  {ci !== x ? (
                    // 이웃 화면은 **자리표시만**. 내용은 열 때 만든다(JIT).
                    <div className="matrix-block">
                      <div className="fv-card fv-placeholder">
                        <p className="fv-placeholder-label">{col.label}</p>
                        <p className="fv-placeholder-title">{col.section.title}</p>
                      </div>
                    </div>
                  ) : (
                    cells.map((i) => (
                      <div
                        key={i}
                        className={clsx("matrix-block", i === y && "active")}
                      >
                        <div className="fv-card">
                          {loading || !steps.length ? (
                            <p className="fv-loading">학습 내용을 준비하는 중…</p>
                          ) : i < steps.length ? (
                            renderStep(i)
                          ) : (
                            renderTail()
                          )}
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* 방향 버튼. 키보드를 모르는 사람도 움직일 수 있어야 한다 —
          몰입 모드는 평소 UI를 다 걷어낸 화면이라 단서가 이것뿐이다. */}
      <div className="focus-nav-2d">
        <button
          type="button"
          onClick={() => goTo(x - 1)}
          disabled={!canEnter(x - 1)}
          aria-label="이전 화면"
        >
          <ArrowLeftIcon />
        </button>
        <button
          type="button"
          onClick={() => moveY(-1)}
          disabled={y <= 0}
          aria-label="이전 개념"
        >
          <ArrowUpIcon />
        </button>
        <button
          type="button"
          onClick={() => moveY(1)}
          disabled={y >= cellCount - 1}
          aria-label="다음 개념"
        >
          <ArrowDownIcon />
        </button>
        <button
          type="button"
          onClick={() => goTo(x + 1)}
          disabled={!canEnter(x + 1)}
          aria-label="다음 화면"
        >
          <ArrowRightIcon />
        </button>
      </div>

      <p className="fv-progress">
        {here?.label} · {Math.min(y + 1, cellCount)} / {cellCount}
      </p>

      {minimapOpen && (
        <>
          <div className="minimap-backdrop" onClick={() => setMinimapOpen(false)} />
          <div className="focus-minimap-2d">
            {groupByChapter(columns).map(([chapterTitle, group]) => (
              <div key={chapterTitle} className="minimap-chapter-col">
                <p className="minimap-chapter-title">{chapterTitle}</p>
                {group.map(({ col, index }) => (
                  <button
                    key={col.section.sectionId}
                    type="button"
                    className={clsx(
                      "minimap-dot",
                      index === x && "active",
                      col.section.status === "solid" && "completed",
                    )}
                    onClick={() => goTo(index)}
                    title={col.section.title}
                  >
                    {col.section.status === "solid" ? <CheckCircleIcon /> : col.label}
                  </button>
                ))}
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

function groupByChapter(columns: FocusColumn[]) {
  const out = new Map<string, { col: FocusColumn; index: number }[]>();
  columns.forEach((col, index) => {
    const key = col.chapter.title;
    out.set(key, [...(out.get(key) ?? []), { col, index }]);
  });
  return [...out.entries()];
}
