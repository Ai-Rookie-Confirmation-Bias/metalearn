import { ChartLineUpIcon } from "@phosphor-icons/react";

// 메타인지 분석 — GET /courses/:id/mastery(개념별 숙련도) 자리.
// 목업 미정: 셸 안에서 본문만 교체되는 걸 보여주는 가벼운 placeholder.
export function AnalysisPage() {
  return (
    <div className="mx-auto w-full max-w-[1400px] px-12 py-12">
      <div className="mb-10">
        <h2 className="mb-1 text-[2rem] font-extrabold tracking-tight text-text-primary">
          메타인지 분석
        </h2>
        <p className="text-text-secondary">개념별 숙련도와 취약점을 한눈에 확인하세요.</p>
      </div>

      <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-border-primary bg-white py-24 text-center">
        <ChartLineUpIcon className="mb-4 text-[3rem] text-text-tertiary" />
        <p className="font-semibold text-text-secondary">곧 제공됩니다</p>
        <p className="mt-1 text-[0.9rem] text-text-tertiary">개념 숙련도 분석을 준비 중이에요.</p>
      </div>
    </div>
  );
}
