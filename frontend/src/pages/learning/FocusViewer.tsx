import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowLeftIcon,
  ArrowRightIcon,
  ArrowUpIcon,
  ArrowDownIcon,
  CaretLeftIcon,
  CheckCircleIcon,
  LockKeyIcon,
  SparkleIcon,
} from "@phosphor-icons/react";
import { clsx } from "clsx";

import { BlockRenderer } from "@/features/learning/blocks/registry";
import type { OnAnswer } from "@/features/learning/blocks/types";
import type { LearningBlock } from "@/features/learning/blocks/types";
import type { AttemptResponse } from "@/features/learning/api/submitAttempt";
import type { TreeChapter, TreeSection } from "@/features/learning/api/getCourseTree";

import "./focus.css";

// 몰입 학습 모드 — UXUI_ANT/focus.html의 2D 매트릭스 뷰어(X=절, Y=블록) 포팅.
// 목업은 전 챕터×블록이 정적으로 존재했지만 실제는 JIT 생성·절 잠금이 있어
// 활성 절만 실블록을 렌더하고, 이웃 절은 자리표시 카드로 조망을 채운다.
// 채점·게이트·신호는 일반 모드와 동일한 서버 라운드트립을 그대로 쓴다.

type Column = { section: TreeSection; chapter: TreeChapter; label: string };

// 목업의 renderMatrix 타이밍(줌아웃 0.4s → 슬라이드 → 줌인 0.5s → 안착 0.6s)
const ZOOM_PAN_MS = 400;
const ZOOM_IN_MS = 500;
const SETTLE_MS = 600;

export function FocusViewer({
  chapters,
  currentSectionId,
  onNavigate,
  blocks,
  blocksLoading,
  waitingGeneration,
  genFailed,
  onRetryGenerate,
  generatePending,
  onAnswer,
  unlocked,
  hasTracked,
  hasNext,
  onNext,
  onReadComplete,
  readCompletePending,
  signal,
  onExit,
}: {
  chapters: TreeChapter[];
  currentSectionId: string | null;
  onNavigate: (sectionId: string) => void;
  blocks: LearningBlock[];
  blocksLoading: boolean;
  waitingGeneration: boolean;
  genFailed: boolean;
  onRetryGenerate: () => void;
  generatePending: boolean;
  onAnswer: OnAnswer;
  unlocked: boolean;
  hasTracked: boolean;
  hasNext: boolean;
  onNext: () => void;
  onReadComplete: () => void;
  readCompletePending: boolean;
  signal: AttemptResponse | null;
  onExit: () => void;
}) {
  // X축 컬럼 = 코스의 전 절(챕터 순회 평탄화) + 미니맵 라벨(장.절)
  const columns = useMemo<Column[]>(
    () =>
      chapters.flatMap((c, ci) =>
        c.sections.map((s, si) => ({ section: s, chapter: c, label: `${ci + 1}.${si + 1}` })),
      ),
    [chapters],
  );
  const x = Math.max(
    0,
    columns.findIndex((c) => c.section.id === currentSectionId),
  );
  const [y, setY] = useState(0);
  const [zoomedOut, setZoomedOut] = useState(false);
  const [minimapOpen, setMinimapOpen] = useState(false);
  const animatingRef = useRef(false);
  const columnRefs = useRef<(HTMLDivElement | null)[]>([]);

  // 활성 절의 셀 수 — 실블록들 + 마지막 게이트 카드 1개(로딩/생성중엔 상태 카드 1개)
  const showStateCard = blocksLoading || blocks.length === 0;
  const cellCount = showStateCard ? 1 : blocks.length + 1;

  const scrollToCell = useCallback(
    (targetY: number, smooth: boolean) => {
      const col = columnRefs.current[x];
      if (!col) return;
      const cells = col.querySelectorAll<HTMLElement>(".matrix-block");
      const cell = cells[targetY];
      if (cell) {
        cell.scrollIntoView({ behavior: smooth ? "smooth" : "auto", block: "center" });
      }
    },
    [x],
  );

  // Y 변경 → 해당 셀을 정중앙으로. 프로그램 스크롤 중엔 수동 동기화를 막아
  // (스크롤 이벤트가 y를 되돌리는 경합 방지) 스냅과 협동한다.
  const programmaticRef = useRef(false);
  useEffect(() => {
    programmaticRef.current = true;
    scrollToCell(y, true);
    const t = window.setTimeout(() => {
      programmaticRef.current = false;
    }, 800);
    return () => window.clearTimeout(t);
  }, [y, scrollToCell]);

  // 절 전환·블록 도착 시 첫 셀부터 (스크롤 위치 리셋)
  useEffect(() => {
    setY(0);
    const raf = requestAnimationFrame(() => scrollToCell(0, false));
    return () => cancelAnimationFrame(raf);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentSectionId, showStateCard, blocks.length]);

  // 수동 스크롤(휠·터치) ↔ y 상태 동기화: 스크롤이 멎은 뒤(디바운스) 뷰포트
  // 중앙에 가장 가까운 셀을 활성으로. 즉시 갱신하면 프로그램 스크롤과 경합한다.
  const scrollSyncTimer = useRef<number | null>(null);
  const onColumnScroll = () => {
    if (animatingRef.current || programmaticRef.current) return;
    if (scrollSyncTimer.current) window.clearTimeout(scrollSyncTimer.current);
    scrollSyncTimer.current = window.setTimeout(() => {
      const col = columnRefs.current[x];
      if (!col) return;
      const center = col.scrollTop + col.clientHeight / 2;
      const cells = Array.from(col.querySelectorAll<HTMLElement>(".matrix-block"));
      let best = 0;
      let bestDist = Infinity;
      cells.forEach((cell, i) => {
        const cellCenter = cell.offsetTop + cell.offsetHeight / 2;
        const d = Math.abs(cellCenter - center);
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
    const newY = y + delta;
    if (newY >= 0 && newY < cellCount) setY(newY);
  };

  // 가로 이동 — 목업의 Zoom → Pan → Zoom 연출. 잠긴 절로는 못 들어간다(서버 잠금 미러).
  const canEnter = (i: number) => i >= 0 && i < columns.length && !columns[i].section.locked;

  const moveX = (delta: number) => {
    if (animatingRef.current) return;
    const newX = x + delta;
    if (!canEnter(newX)) return;
    animatingRef.current = true;
    setZoomedOut(true);
    window.setTimeout(() => {
      onNavigate(columns[newX].section.id); // x는 currentSectionId에서 파생 → 트랙 슬라이드
      window.setTimeout(() => {
        setZoomedOut(false);
        window.setTimeout(() => {
          animatingRef.current = false;
        }, SETTLE_MS);
      }, ZOOM_IN_MS);
    }, ZOOM_PAN_MS);
  };

  const jumpTo = (i: number) => {
    if (animatingRef.current || i === x || !canEnter(i)) return;
    setMinimapOpen(false);
    animatingRef.current = true;
    setZoomedOut(true);
    window.setTimeout(() => {
      onNavigate(columns[i].section.id);
      window.setTimeout(() => {
        setZoomedOut(false);
        window.setTimeout(() => {
          animatingRef.current = false;
        }, SETTLE_MS);
      }, ZOOM_IN_MS);
    }, ZOOM_PAN_MS);
  };

  // 키보드: ↑↓ 블록, ←→ 절, ESC 종료 — 입력 중(cloze/서답형)엔 무시
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement;
      if (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.isContentEditable) {
        if (e.key === "Escape") t.blur();
        return;
      }
      if (e.key === "Escape") {
        onExit();
        return;
      }
      if (animatingRef.current) return;
      if (e.key === "ArrowUp") {
        e.preventDefault();
        moveY(-1);
      } else if (e.key === "ArrowDown") {
        e.preventDefault();
        moveY(1);
      } else if (e.key === "ArrowLeft") {
        e.preventDefault();
        moveX(-1);
      } else if (e.key === "ArrowRight") {
        e.preventDefault();
        moveX(1);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  const current = columns[x];

  return (
    <div className="focus-root">
      {/* 상단 바 */}
      <div className="focus-top-bar">
        <button type="button" className="focus-exit" onClick={onExit}>
          <CaretLeftIcon weight="fill" /> 일반 학습으로 돌아가기
        </button>
      </div>

      {/* 미니맵 확장 시 플리커 방지 히트박스 */}
      <div
        className={clsx("minimap-overlay-hitbox", minimapOpen && "active")}
        onMouseLeave={() => setMinimapOpen(false)}
      />

      {/* 우측 상단 2D 미니맵 */}
      <div
        className={clsx("focus-minimap-2d", minimapOpen && "expanded")}
        onMouseEnter={() => setMinimapOpen(true)}
      >
        {columns.map((col, i) => {
          const dots = i === x ? cellCount : 1;
          return (
            <div className="minimap-chapter-col" key={col.section.id}>
              <div className="minimap-chapter-title">{col.label}</div>
              {Array.from({ length: dots }).map((_, dy) => (
                <button
                  type="button"
                  // eslint-disable-next-line react/no-array-index-key
                  key={dy}
                  title={`${col.chapter.title} — ${col.section.title}`}
                  className={clsx(
                    "minimap-dot",
                    i === x && dy === y && "active",
                    col.section.locked && "locked",
                    (col.section.progressStatus === "completed" ||
                      (i === x && dy < y)) &&
                      !(i === x && dy === y) &&
                      "completed",
                  )}
                  onClick={(e) => {
                    e.stopPropagation();
                    if (i === x) setY(dy);
                    else jumpTo(i);
                  }}
                />
              ))}
            </div>
          );
        })}
      </div>

      {/* 메인 2D 뷰포트 */}
      <div className="matrix-viewport">
        <div className={clsx("matrix-map", zoomedOut && "zoomed-out")}>
          <div
            className="matrix-x-track"
            style={{ transform: `translateX(-${x * 100}vw)` }}
          >
            {columns.map((col, i) => (
              <div
                className="matrix-chapter"
                key={col.section.id}
                ref={(el) => {
                  columnRefs.current[i] = el;
                }}
                onScroll={i === x ? onColumnScroll : undefined}
              >
                <div className="matrix-y-track">
                  {i === x ? (
                    showStateCard ? (
                      // 로딩/생성중/실패 상태 카드 (일반 모드와 동일 판정)
                      <div className="matrix-block active">
                        <div className="learning-block-wrapper">
                          <div className="focus-chapter-title-inline">
                            {col.chapter.title} · {col.section.title}
                          </div>
                          <div className="fv-placeholder">
                            {genFailed ? (
                              <>
                                <div className="fv-placeholder-title">
                                  콘텐츠 생성에 실패했어요
                                </div>
                                <button
                                  type="button"
                                  onClick={onRetryGenerate}
                                  disabled={generatePending}
                                  className="mt-4 rounded-xl bg-primary px-5 py-2 text-[0.9rem] font-semibold text-white disabled:opacity-50"
                                >
                                  {generatePending ? "다시 생성 중…" : "다시 생성하기"}
                                </button>
                              </>
                            ) : waitingGeneration ? (
                              <>
                                <SparkleIcon className="mx-auto mb-3 text-3xl" weight="fill" />
                                <div className="fv-placeholder-title">
                                  AI가 학습 콘텐츠를 만들고 있어요
                                </div>
                                보통 1~2분 걸려요. 완성되면 자동으로 열려요.
                              </>
                            ) : (
                              "불러오는 중…"
                            )}
                          </div>
                        </div>
                      </div>
                    ) : (
                      <>
                        {blocks.map((block, bi) => (
                          <div
                            className={clsx("matrix-block", bi === y && "active")}
                            key={block.id}
                          >
                            <div className="learning-block-wrapper">
                              {bi === 0 && (
                                <div className="focus-chapter-title-inline">
                                  {col.chapter.title} · {col.section.title}
                                </div>
                              )}
                              <div className="fv-card">
                                <BlockRenderer block={block} onAnswer={onAnswer} />
                              </div>
                            </div>
                          </div>
                        ))}
                        {/* 마지막 셀 = 진행 게이트(서버 판정 미러) — 일반 모드와 동일 규칙 */}
                        <div
                          className={clsx(
                            "matrix-block",
                            y === blocks.length && "active",
                          )}
                        >
                          <div className="learning-block-wrapper">
                            <div className="fv-placeholder">
                              {!hasTracked && !unlocked ? (
                                <>
                                  <div className="fv-placeholder-title">
                                    <CheckCircleIcon
                                      className="mb-1 inline text-[#10b981]"
                                      weight="fill"
                                    />{" "}
                                    읽기만으로 완료할 수 있는 절이에요
                                  </div>
                                  <button
                                    type="button"
                                    onClick={onReadComplete}
                                    disabled={readCompletePending}
                                    className="mt-4 rounded-xl bg-primary px-6 py-2.5 text-[0.9rem] font-semibold text-white disabled:opacity-50"
                                  >
                                    {readCompletePending
                                      ? "완료 처리 중…"
                                      : "다 읽었어요 · 계속하기"}
                                  </button>
                                </>
                              ) : unlocked ? (
                                <>
                                  <div className="fv-placeholder-title">
                                    <CheckCircleIcon
                                      className="mb-1 inline text-[#10b981]"
                                      weight="fill"
                                    />{" "}
                                    모든 인출을 완료했습니다
                                  </div>
                                  <button
                                    type="button"
                                    onClick={hasNext ? () => moveX(1) : onNext}
                                    className="mt-4 rounded-xl bg-primary px-6 py-2.5 text-[0.9rem] font-semibold text-white"
                                  >
                                    {hasNext ? "다음 강의로 넘어가기" : "코스 완료하기"}
                                  </button>
                                </>
                              ) : (
                                <>
                                  <LockKeyIcon className="mx-auto mb-2 text-2xl" weight="fill" />
                                  위의 모든 인출 문제에 답해야 다음으로 진행할 수 있어요.
                                </>
                              )}
                            </div>
                          </div>
                        </div>
                      </>
                    )
                  ) : (
                    // 이웃 절 자리표시 — 줌아웃 조망·슬라이드 중에 보이는 카드
                    <div className={clsx("matrix-block", "active")}>
                      <div className="learning-block-wrapper">
                        <div className="focus-chapter-title-inline">
                          {col.chapter.title} · {col.section.title}
                        </div>
                        <div className="fv-placeholder">
                          {col.section.locked ? (
                            <>
                              <LockKeyIcon className="mx-auto mb-2 text-2xl" weight="fill" />
                              이전 절을 완료하면 열려요
                            </>
                          ) : col.section.progressStatus === "completed" ? (
                            <>
                              <CheckCircleIcon
                                className="mx-auto mb-2 text-2xl text-[#10b981]"
                                weight="fill"
                              />
                              완료한 절이에요 — 이동하면 다시 볼 수 있어요
                            </>
                          ) : (
                            "이동하면 이 절의 학습 블록이 열려요"
                          )}
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* 살아있는 커리큘럼 신호 — 몰입 중에도 말없이 변하지 않는다 */}
      {signal?.prerequisite && (
        <div className="fv-signal">
          <span>
            선수 개념 결손 감지 — <b>{signal.prerequisite.title}</b>을(를) 먼저 다지면 쉬워져요
          </span>
          <button
            type="button"
            onClick={() => onNavigate(signal.prerequisite!.sectionId)}
          >
            선행 먼저 학습
          </button>
        </div>
      )}
      {!signal?.prerequisite && signal?.resumeSectionId && (
        <div className="fv-signal resume">
          <span>선행 학습을 마쳤어요 — 원래 절로 돌아갈까요?</span>
          <button type="button" onClick={() => onNavigate(signal.resumeSectionId!)}>
            원래 절로 복귀
          </button>
        </div>
      )}

      {/* 이동 컨트롤 (우측 하단) — 목업 focus-nav-2d */}
      <div className="focus-nav-2d">
        <button
          type="button"
          aria-label="이전 절"
          disabled={!canEnter(x - 1)}
          onClick={() => moveX(-1)}
        >
          <ArrowLeftIcon />
        </button>
        <button type="button" aria-label="위 블록" disabled={y === 0} onClick={() => moveY(-1)}>
          <ArrowUpIcon />
        </button>
        <button
          type="button"
          aria-label="아래 블록"
          disabled={y >= cellCount - 1}
          onClick={() => moveY(1)}
        >
          <ArrowDownIcon />
        </button>
        <button
          type="button"
          aria-label="다음 절"
          disabled={!canEnter(x + 1)}
          onClick={() => moveX(1)}
        >
          <ArrowRightIcon />
        </button>
      </div>

      {/* 현재 위치 표시 (좌측 하단) */}
      <div className="absolute bottom-8 left-8 z-[1205] text-[0.85rem] font-semibold text-white/50">
        {current ? `${current.label} · ${current.section.title}` : ""}
        {!showStateCard && cellCount > 1 && (
          <span className="ml-2 text-white/30">
            {Math.min(y + 1, cellCount)}/{cellCount}
          </span>
        )}
      </div>
    </div>
  );
}
