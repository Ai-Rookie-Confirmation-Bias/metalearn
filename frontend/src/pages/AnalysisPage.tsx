import { ChartLineUpIcon } from "@phosphor-icons/react";
import { clsx } from "clsx";

import { useCourses } from "@/features/library/queries/useCourses";
import { useMastery } from "@/features/analysis/queries/useMastery";
import type { ConceptMasteryItem } from "@/features/analysis/api/getMastery";

// 메타인지 분석 — GET /courses/:id/mastery(개념별 숙련도 + 상태별 요약).
const STATUS: Record<
  ConceptMasteryItem["status"],
  { label: string; dot: string; text: string }
> = {
  mastered: { label: "완료", dot: "bg-[#10b981]", text: "text-[#047857]" },
  learning: { label: "학습 중", dot: "bg-[#3b82f6]", text: "text-[#1d4ed8]" },
  todo: { label: "예정", dot: "bg-[#f59e0b]", text: "text-[#b45309]" },
  locked: { label: "잠금", dot: "bg-text-tertiary", text: "text-text-tertiary" },
};

function StatTile({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className="flex flex-col gap-1 rounded-2xl border border-border-primary bg-white p-5">
      <span className="text-[0.85rem] font-semibold text-text-secondary">{label}</span>
      <span className={clsx("text-[1.8rem] font-extrabold tabular-nums", color)}>{value}</span>
    </div>
  );
}

export function AnalysisPage() {
  const { data: courses } = useCourses();
  const courseId = courses?.[0]?.id;
  const { data, isLoading } = useMastery(courseId);

  return (
    <div className="mx-auto w-full max-w-[1400px] px-12 py-12">
      <div className="mb-10">
        <h2 className="mb-1 text-[2rem] font-extrabold tracking-tight text-text-primary">
          메타인지 분석
        </h2>
        <p className="text-text-secondary">개념별 숙련도와 취약점을 한눈에 확인하세요.</p>
      </div>

      {isLoading || !data ? (
        <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-border-primary bg-white py-24 text-center">
          <ChartLineUpIcon className="mb-4 text-[3rem] text-text-tertiary" />
          <p className="font-semibold text-text-secondary">
            {courseId ? "숙련도 불러오는 중…" : "코스가 없습니다."}
          </p>
        </div>
      ) : (
        <>
          <div className="mb-8 grid grid-cols-2 gap-4 sm:grid-cols-4">
            <StatTile label="완료" value={data.mastered} color="text-[#047857]" />
            <StatTile label="학습 중" value={data.learning} color="text-[#1d4ed8]" />
            <StatTile label="예정" value={data.todo} color="text-[#b45309]" />
            <StatTile label="잠금" value={data.locked} color="text-text-tertiary" />
          </div>

          <div className="overflow-hidden rounded-2xl border border-border-primary bg-white">
            <div className="border-b border-border-primary px-6 py-4 text-[0.9rem] font-bold text-text-secondary">
              개념별 숙련도 ({data.concepts.length})
            </div>
            <ul>
              {data.concepts.map((c) => {
                const st = STATUS[c.status];
                return (
                  <li
                    key={c.conceptId}
                    className="flex items-center gap-4 border-b border-border-primary px-6 py-4 last:border-b-0"
                  >
                    <span className={clsx("h-2.5 w-2.5 shrink-0 rounded-full", st.dot)} />
                    <div className="w-48 shrink-0">
                      <div className="font-semibold text-text-primary">{c.name}</div>
                      <div className={clsx("text-[0.8rem] font-medium", st.text)}>{st.label}</div>
                    </div>
                    <div className="flex-1">
                      <div className="h-2 overflow-hidden rounded-full bg-bg-secondary">
                        <div
                          className="h-full rounded-full bg-primary transition-all"
                          style={{ width: `${Math.round(c.strength * 100)}%` }}
                        />
                      </div>
                    </div>
                    <span className="w-12 shrink-0 text-right text-[0.85rem] font-semibold tabular-nums text-text-secondary">
                      {Math.round(c.strength * 100)}%
                    </span>
                  </li>
                );
              })}
            </ul>
          </div>
        </>
      )}
    </div>
  );
}
