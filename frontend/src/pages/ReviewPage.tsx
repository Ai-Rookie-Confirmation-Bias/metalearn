import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { ArrowClockwiseIcon, CheckCircleIcon } from "@phosphor-icons/react";

import { BlockRenderer } from "@/features/learning/blocks/registry";
import type { AnswerEvent, AttemptResult, OnAnswer } from "@/features/learning/blocks/types";
import type { ReviewDueItem } from "@/features/review/api/getReviewDue";
import { useReviewDue } from "@/features/review/queries/useReviewDue";
import { useSubmitReviewAnswer } from "@/features/review/queries/useSubmitReviewAnswer";

// 복습 화면 — 도래 개념을 같은 봉투 렌더러로 다시 인출. 채점·재스케줄은 서버(POST /review/answer).
export function ReviewPage() {
  const queryClient = useQueryClient();
  const { data } = useReviewDue();
  const submit = useSubmitReviewAnswer();

  // 세션 스냅샷 — 답하면 서버가 재스케줄해 목록에서 빠지므로, 화면은 처음 목록을 고정.
  const [items, setItems] = useState<ReviewDueItem[] | null>(null);
  const [doneIds, setDoneIds] = useState<Set<string>>(new Set());

  useEffect(() => {
    if (data && items === null) setItems(data.items.filter((i) => i.block));
  }, [data, items]);

  const onAnswer: OnAnswer = async (e: AnswerEvent): Promise<AttemptResult> => {
    const r = await submit.mutateAsync(e);
    if (r.correct) {
      setDoneIds((prev) => new Set(prev).add(e.conceptId));
      queryClient.invalidateQueries({ queryKey: ["reviewDue"] }); // 배지 갱신
    }
    return r;
  };

  return (
    <div className="mx-auto w-full max-w-[900px] px-12 py-12">
      <div className="mb-10">
        <h2 className="mb-1 text-[2rem] font-extrabold tracking-tight text-text-primary">복습</h2>
        <p className="text-text-secondary">망각곡선에 따라 지금 다시 꺼내볼 개념들이에요.</p>
      </div>

      {items === null ? (
        <div className="py-24 text-center text-text-tertiary">불러오는 중…</div>
      ) : items.length === 0 ? (
        <div className="flex flex-col items-center rounded-2xl border border-dashed border-border-primary bg-white py-24 text-center">
          <CheckCircleIcon weight="fill" className="mb-4 text-[3rem] text-[#10b981]" />
          <p className="font-semibold text-text-secondary">복습할 개념이 없어요 🎉</p>
          <p className="mt-1 text-[0.9rem] text-text-tertiary">다음 도래 때 다시 소환할게요.</p>
        </div>
      ) : (
        <div className="flex flex-col gap-6">
          {items.map((item) => {
            const done = doneIds.has(item.conceptId);
            return (
              <div
                key={item.conceptId}
                className="rounded-2xl border border-border-primary bg-white p-6"
              >
                <div className="mb-4 flex items-center gap-2">
                  <ArrowClockwiseIcon className="text-accent" />
                  <span className="font-bold text-text-primary">{item.conceptName}</span>
                  {done && (
                    <span className="ml-auto text-[0.85rem] font-semibold text-[#047857]">
                      ✅ 복습 완료
                    </span>
                  )}
                </div>
                {done ? (
                  <p className="text-[0.9rem] text-text-tertiary">
                    잘 기억하고 있어요. 다음 복습 때 또 만나요.
                  </p>
                ) : (
                  item.block && <BlockRenderer block={item.block} onAnswer={onAnswer} />
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
