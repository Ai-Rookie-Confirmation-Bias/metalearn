import { useState } from "react";
import { clsx } from "clsx";
import {
  CaretDownIcon,
  CaretUpIcon,
  CheckCircleIcon,
  PlayCircleIcon,
  LockSimpleIcon,
} from "@phosphor-icons/react";

import type { Chapter } from "./mock";

// 좌측 커리큘럼(목차) — 표시 전부 데이터 파생:
//   완료 = completedIds / 현재 = currentSectionId / 잠김 = 이전 레슨 미완료
//   진도율 = 완료 수 ÷ 전체 수. 레슨 클릭 → onSelect (잠긴 레슨은 불가)
export function CurriculumPanel({
  chapters,
  currentSectionId,
  completedIds,
  unlockedIds,
  onSelect,
}: {
  chapters: Chapter[];
  currentSectionId: string;
  completedIds: Set<string>;
  unlockedIds: Set<string>;
  onSelect: (sectionId: string) => void;
}) {
  // 현재 절이 속한 챕터는 기본으로 펼침
  const [open, setOpen] = useState(
    () =>
      new Set(
        chapters.filter((c) => c.sections.some((l) => l.id === currentSectionId)).map((c) => c.id),
      ),
  );

  const totalSections = chapters.reduce((n, c) => n + c.sections.length, 0);
  const progress = totalSections ? Math.round((completedIds.size / totalSections) * 100) : 0;

  const toggle = (id: string) =>
    setOpen((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  return (
    <aside className="flex w-[300px] flex-shrink-0 flex-col border-r border-border-primary bg-white">
      <div className="flex items-center justify-between border-b border-border-primary px-6 py-4">
        <h3 className="font-bold text-text-primary">커리큘럼</h3>
        <div className="flex items-center gap-2">
          <span className="text-[0.8rem] font-semibold text-text-secondary">진도율 {progress}%</span>
          <div className="h-1.5 w-[60px] overflow-hidden rounded-full bg-border-primary">
            <div
              className="h-full rounded-full bg-primary transition-all duration-500"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        {chapters.map((ch) => {
          const isOpen = open.has(ch.id);
          // 챕터 완료 = 소속 절 전부 완료
          const chapterDone = ch.sections.every((l) => completedIds.has(l.id));
          return (
            <div key={ch.id} className="border-b border-border-primary">
              <button
                type="button"
                onClick={() => toggle(ch.id)}
                className={clsx(
                  "flex w-full items-center justify-between px-6 py-4 text-left",
                  isOpen ? "bg-white" : "bg-bg-secondary",
                )}
              >
                <div className="min-w-0 flex-1">
                  <h4 className="flex items-center gap-1.5 text-[0.95rem] font-bold text-text-primary">
                    {ch.origin === "prereq" && (
                      <span className="shrink-0 rounded-md bg-[#f59e0b]/15 px-1.5 py-0.5 text-[0.68rem] font-bold text-[#b45309]">
                        선행
                      </span>
                    )}
                    <span className="truncate">{ch.title}</span>
                    {chapterDone && (
                      <CheckCircleIcon weight="fill" className="shrink-0 text-[#10b981]" />
                    )}
                  </h4>
                  {/* 이유 라벨(서버 우선) — 이 장이 왜 끼워졌는지 */}
                  {ch.origin === "prereq" && (ch.reason || ch.prereqForTitle) && (
                    <p
                      className="mt-0.5 truncate text-[0.72rem] text-text-tertiary"
                      title={ch.reason ?? undefined}
                    >
                      {ch.reason ?? `↳ ${ch.prereqForTitle} 준비`}
                    </p>
                  )}
                </div>
                {isOpen ? (
                  <CaretUpIcon className="text-text-tertiary" />
                ) : (
                  <CaretDownIcon className="text-text-tertiary" />
                )}
              </button>
              {isOpen && (
                <div className="py-2">
                  {ch.sections.map((l) => {
                    const done = completedIds.has(l.id);
                    const active = l.id === currentSectionId;
                    const locked = !unlockedIds.has(l.id);
                    return (
                      <button
                        key={l.id}
                        type="button"
                        disabled={locked}
                        onClick={() => onSelect(l.id)}
                        className={clsx(
                          "flex w-full items-center gap-3 px-6 py-3 text-left transition-colors",
                          active && "bg-accent/5",
                          locked ? "cursor-not-allowed opacity-60" : "hover:bg-bg-secondary",
                        )}
                      >
                        {done ? (
                          <CheckCircleIcon weight="fill" className="shrink-0 text-xl text-[#10b981]" />
                        ) : locked ? (
                          <LockSimpleIcon className="shrink-0 text-xl text-text-tertiary" />
                        ) : (
                          <PlayCircleIcon weight="fill" className="shrink-0 text-xl text-accent" />
                        )}
                        <span
                          className={clsx(
                            "flex-1 truncate text-[0.9rem]",
                            active ? "font-semibold text-accent" : "text-text-secondary",
                          )}
                        >
                          {l.title}
                        </span>
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </aside>
  );
}
