import { BrainIcon, SparkleIcon } from "@phosphor-icons/react";

// 흐름 제어: 망각곡선 복습 팝업 — 다음 절로 넘어가기 전 복습 도래 개념을 소환.
// 데이터는 GET /review/due (concept_mastery.next_due_at ≤ now). 지금은 mock 주입.
export type ReviewDueItem = { concept: string; learnedAgo: string };

export function ReviewGateModal({
  items,
  onStart,
  onLater,
}: {
  items: ReviewDueItem[];
  onStart: () => void;
  onLater: () => void;
}) {
  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-[#0f172a]/80 px-4 backdrop-blur-sm">
      <div className="w-full max-w-[500px] rounded-2xl bg-white p-10 text-center shadow-[0_25px_50px_-12px_rgba(0,0,0,0.25)]">
        <BrainIcon weight="fill" className="mx-auto mb-4 text-[3.5rem] text-[#6366f1]" />
        <h2 className="mb-2 text-[1.75rem] font-extrabold text-primary">잠깐, 복습할 시간이에요!</h2>
        <p className="mb-8 leading-relaxed text-text-secondary">
          다음 강의로 넘어가기 전,
          <br />
          망각 곡선에 따라 잊어버리기 쉬운 {items.length}가지 개념을 짚고 넘어갑니다.
        </p>

        <div className="mb-8 flex flex-col gap-3 rounded-xl bg-bg-secondary p-6 text-left">
          {items.map((it) => (
            <div key={it.concept} className="flex items-center gap-3 font-semibold text-text-primary">
              <SparkleIcon weight="fill" className="text-xl text-[#f59e0b]" />
              {it.concept} <span className="font-medium text-text-tertiary">({it.learnedAgo} 학습)</span>
            </div>
          ))}
        </div>

        <button
          type="button"
          onClick={onStart}
          className="w-full rounded-xl bg-primary py-3 text-[0.95rem] font-semibold text-white shadow-sm transition-all hover:-translate-y-0.5 hover:bg-primary-hover hover:shadow-md"
        >
          복습 퀴즈 시작하기
        </button>
        <button
          type="button"
          onClick={onLater}
          className="mt-2 w-full rounded-xl py-3 text-[0.95rem] font-semibold text-text-tertiary transition-colors hover:text-text-secondary"
        >
          다음에 할게요
        </button>
      </div>
    </div>
  );
}
