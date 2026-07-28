import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { clsx } from "clsx";
import {
  ArrowLeftIcon,
  ArrowRightIcon,
  ArrowsOutSimpleIcon,
  LockKeyIcon,
  CheckCircleIcon,
  ListIcon,
} from "@phosphor-icons/react";

import { BlockRenderer } from "@/features/learning/blocks/registry";
import { ReviewGateModal } from "@/features/learning/blocks/ReviewGateModal";
import type { AnswerEvent } from "@/features/learning/blocks/types";
import { CurriculumPanel } from "@/pages/learning/CurriculumPanel";
import { AiTutorPanel } from "@/pages/learning/AiTutorPanel";
import { course, initialCompletedSectionIds, reviewDue } from "@/pages/learning/mock";

// 학습 화면 — UXUI_ANT/learning.html 기준 3컬럼(커리큘럼 / 블록 / AI튜터·노트).
// 화면의 모든 표시는 데이터에서 파생: 진도율=완료÷전체, 잠금=이전 레슨 완료 여부,
// 레슨 클릭=해당 절 블록 로드, 인출 전부 정답→완료 처리→진도율↑→다음 레슨 열림.
export function LearningPage() {
  const flatSections = useMemo(() => course.chapters.flatMap((c) => c.sections), []);

  // 완료된 레슨 (초기값 = 서버 section_progress mock) — "다음 강의" 시 갱신
  const [completedIds, setCompletedIds] = useState(() => new Set(initialCompletedSectionIds));
  // 현재 보고 있는 레슨 = 첫 미완료 레슨부터
  const [currentSectionId, setCurrentSectionId] = useState(
    () => flatSections.find((l) => !completedIds.has(l.id))?.id ?? flatSections[0].id,
  );
  // 레슨별로 정답 처리된 tracked 블록 id (레슨을 오가도 유지)
  const [solvedBySection, setSolvedBySection] = useState<Record<string, Set<string>>>({});
  const [showReviewGate, setShowReviewGate] = useState(false);

  // ── 파생 값들 ──
  const currentSection = flatSections.find((l) => l.id === currentSectionId)!;
  const currentIndex = flatSections.findIndex((l) => l.id === currentSectionId);
  const nextSection = flatSections[currentIndex + 1];

  // 잠금 해제된 레슨 = 완료된 레슨 + 그 바로 다음(첫 미완료)까지
  const unlockedIds = useMemo(() => {
    const ids = new Set<string>();
    for (const l of flatSections) {
      ids.add(l.id);
      if (!completedIds.has(l.id)) break; // 첫 미완료까지 열고 그 뒤는 잠금
    }
    return ids;
  }, [flatSections, completedIds]);

  // 게이트: 이미 완료한 레슨이면 통과, 아니면 tracked 블록 전부 정답이어야
  const solved = solvedBySection[currentSectionId] ?? new Set<string>();
  const trackedIds = currentSection.blocks.filter((b) => b.tracked).map((b) => b.id);
  const unlocked = completedIds.has(currentSectionId) || trackedIds.every((id) => solved.has(id));

  // ②③ 공통 콜백 — 지금은 로컬 수집. 백엔드 붙으면 여기서 POST /attempts 전송
  const onAnswer = (e: AnswerEvent) => {
    if (!e.correct) return;
    setSolvedBySection((prev) => {
      const next = new Set(prev[currentSectionId] ?? []);
      next.add(e.blockId);
      return { ...prev, [currentSectionId]: next };
    });
  };

  // "다음 강의" — 현재 레슨 완료 처리(진도율↑, 다음 레슨 잠금 해제) 후 복습 게이트 소환
  const goNext = () => {
    setCompletedIds((prev) => new Set(prev).add(currentSectionId));
    if (reviewDue.length > 0) setShowReviewGate(true);
    else moveToNext();
  };
  const moveToNext = () => {
    setShowReviewGate(false);
    if (nextSection) setCurrentSectionId(nextSection.id);
  };

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-[#f3f4f6]">
      {/* 상단 학습 헤더 */}
      <header className="z-20 flex h-16 flex-shrink-0 items-center justify-between border-b border-border-primary bg-white px-6">
        <div className="flex items-center gap-6">
          <Link
            to="/library"
            className="flex items-center gap-2 text-[0.9rem] font-semibold text-text-secondary transition-colors hover:text-primary"
          >
            <ArrowLeftIcon /> 책장으로
          </Link>
          <div className="flex items-center gap-4 border-l border-border-primary pl-6">
            <span className="rounded-md bg-bg-secondary px-2.5 py-1 text-xs font-bold text-text-secondary">
              {course.category}
            </span>
            <h1 className="text-[1.1rem] font-bold text-primary">{course.title}</h1>
          </div>
        </div>
        <div className="flex items-center gap-4">
          {/* 몰입 뷰어(focus)는 후속 — 자리만 */}
          <button
            type="button"
            className="flex items-center gap-2 rounded-xl border border-border-primary bg-bg-secondary px-4 py-2 text-[0.85rem] font-semibold text-text-primary transition-colors hover:bg-border-primary/50"
          >
            <ArrowsOutSimpleIcon weight="fill" /> 몰입 뷰어 켜기
          </button>
          <button
            type="button"
            className="flex h-10 w-10 items-center justify-center rounded-full bg-bg-secondary text-xl text-text-secondary"
          >
            <ListIcon />
          </button>
        </div>
      </header>

      {/* 3컬럼 */}
      <div className="flex flex-1 overflow-hidden">
        <CurriculumPanel
          chapters={course.chapters}
          currentSectionId={currentSectionId}
          completedIds={completedIds}
          unlockedIds={unlockedIds}
          onSelect={setCurrentSectionId}
        />

        {/* 중앙: 현재 레슨의 블록 렌더 */}
        <main className="flex-1 overflow-y-auto bg-white" key={currentSectionId}>
          <div className="mx-auto w-full max-w-[1000px] p-12">
            <h2 className="mb-6 text-[2rem] font-extrabold tracking-tight text-text-primary">
              {currentSection.title}
            </h2>

            {currentSection.blocks.map((block) => (
              <BlockRenderer key={`${currentSectionId}-${block.id}`} block={block} onAnswer={onAnswer} />
            ))}

            {/* 잠금 게이트 — tracked 전부 답해야 다음 */}
            <div className="mt-12 flex flex-col items-center gap-4 border-t border-border-primary pt-8">
              {unlocked ? (
                <div className="flex items-center gap-1.5 text-[0.9rem] font-medium text-text-tertiary">
                  <CheckCircleIcon weight="fill" className="text-[#10b981]" /> 모든 인출을 완료했습니다. 다음으로
                  넘어갈 수 있습니다.
                </div>
              ) : (
                <div className="flex items-center gap-1.5 text-[0.9rem] font-medium text-text-tertiary">
                  <LockKeyIcon weight="fill" /> 위의 모든 인출 문제에 답해야 진행할 수 있습니다.
                </div>
              )}
              <button
                type="button"
                onClick={goNext}
                disabled={!unlocked}
                className={clsx(
                  "inline-flex items-center gap-2 rounded-xl px-5 py-[0.6rem] text-[13.3333px] font-semibold leading-[normal] text-white shadow-sm transition-all",
                  unlocked
                    ? "bg-primary hover:-translate-y-0.5 hover:bg-primary-hover hover:shadow-md"
                    : "cursor-not-allowed bg-text-tertiary opacity-70",
                )}
              >
                {nextSection ? "다음 강의로 넘어가기" : "코스 완료하기"} <ArrowRightIcon />
              </button>
            </div>
          </div>
        </main>

        <AiTutorPanel />
      </div>

      {/* 망각곡선 복습 게이트 — 복습 퀴즈 화면은 후속(같은 봉투로 렌더 예정) */}
      {showReviewGate && (
        <ReviewGateModal items={reviewDue} onStart={moveToNext} onLater={moveToNext} />
      )}
    </div>
  );
}
