// [화면 5] 복습 — 망각곡선이 불러온 것들.
//
// ⚠️ **설명은 안 보여준다.** 복습은 잊혀가는 걸 되살리는 자리다. 설명을 다시
//    읽히면 재인이 되어 "읽었으니 안다"는 착각만 늘린다. 문항만 낸다.
//
// ⚠️ **막지 않는다.** integration은 다음 강의로 넘어갈 때 전면 모달로 복습을
//    띄웠다(`ReviewGateModal`). 그쪽은 학습을 잠갔다가 이탈을 겪은 팀이고,
//    게다가 "복습 시작"과 "다음에 할게요"가 같은 함수라 선택이 가짜였다.
//    여기는 들어오는 것도 나가는 것도 학습자가 정한다.
//
// 한 번도 못 맞힌 화면은 여기 없다 — 그건 잊은 게 아니라 아직 모르는 것이라
// 처방이 다르다(보충 화면과 설명 안 ⚡가 맡는다).
import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import { ArrowsClockwiseIcon, ClockCounterClockwiseIcon } from "@phosphor-icons/react";

import type { BlockOut } from "@/features/curriculum/api/curriculum";
import { Cloze } from "@/features/curriculum/components/Cloze";
import { useAnswer, useReview } from "@/features/curriculum/queries/useCurriculum";

// 시연용 시계 이동. 첫 복습은 맞힌 뒤 2.2일에 오는데 발표에서 그걸 기다릴 수 없다.
// **가짜 데이터가 아니라 진짜 곡선을 시간만 옮겨 보는 것**이라 그대로 설명할 수 있다.
const SHIFTS = [0, 3, 7, 14];

export function ReviewPage() {
  const { docId = "" } = useParams<{ docId: string }>();
  const [days, setDays] = useState(0);
  const { data, isLoading } = useReview(docId, days);
  const answer = useAnswer(docId);

  const grade = (sectionId: string) => (correct: boolean, conceptKey?: string) =>
    answer.mutate({ sectionId, correct, conceptKey, kind: "review" });

  return (
    <div className="mx-auto max-w-2xl p-8">
      <Link
        to={`/curriculum/${encodeURIComponent(docId)}`}
        className="text-[0.8rem] text-text-tertiary hover:underline"
      >
        ← 자료로
      </Link>

      <header className="mt-3 mb-6">
        <h1 className="flex items-center gap-2 text-2xl font-bold text-text-primary">
          <ArrowsClockwiseIcon weight="bold" className="text-amber-600" />
          복습
        </h1>
        <p className="mt-1 text-[0.85rem] text-text-secondary">
          맞힌 적 있는데 <b>잊혀가는</b> 화면들입니다. 설명은 안 보여드립니다 —
          읽는 게 아니라 꺼내는 자리예요.
        </p>
      </header>

      {/* 시연용. 곡선은 진짜고 시계만 옮긴다. */}
      <div className="mb-6 flex items-center gap-2 rounded-lg border border-dashed border-border-primary p-3">
        <ClockCounterClockwiseIcon className="text-text-tertiary" />
        <span className="text-[0.75rem] text-text-tertiary">시점</span>
        {SHIFTS.map((d) => (
          <button
            key={d}
            type="button"
            onClick={() => setDays(d)}
            className={`rounded px-2.5 py-1 text-[0.75rem] font-semibold ${
              d === days
                ? "bg-primary text-white"
                : "text-text-secondary hover:bg-bg-secondary"
            }`}
          >
            {d === 0 ? "지금" : `${d}일 뒤`}
          </button>
        ))}
      </div>

      {isLoading && (
        <p className="text-text-secondary">복습 문항을 만드는 중… (화면마다 5초쯤)</p>
      )}

      {data && data.totalDue === 0 && (
        <div className="rounded-lg border border-dashed border-border-primary py-16 text-center">
          <p className="font-semibold text-text-secondary">지금 복습할 게 없습니다</p>
          <p className="mt-1 text-[0.85rem] text-text-tertiary">
            맞힌 뒤 2~3일이 지나야 첫 복습이 옵니다. 위에서 시점을 옮겨보세요.
          </p>
        </div>
      )}

      {data && data.items.length > 0 && (
        <>
          <p className="mb-4 text-[0.8rem] text-text-tertiary">
            복습 대상 {data.totalDue}개 중 {data.items.length}개를 가져왔습니다.
          </p>
          <div className="space-y-6">
            {data.items.map((it) => (
              <section
                key={it.sectionId}
                className="rounded-lg border border-border-primary p-4"
              >
                <div className="flex items-baseline justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-[0.7rem] text-text-tertiary">{it.chapterTitle}</p>
                    <h2 className="font-semibold text-text-primary">{it.title}</h2>
                  </div>
                  {/* 왜 지금 나왔는지. 숫자가 없으면 "왜 이걸 또?"가 된다. */}
                  <p className="flex-shrink-0 text-[0.75rem] font-semibold text-amber-700">
                    {it.daysSince}일 전 · 회상 {Math.round(it.recall * 100)}%
                  </p>
                </div>

                <ul className="mt-3 space-y-3">
                  {it.blocks.map((b: BlockOut, i: number) => (
                    <Cloze
                      key={`${it.sectionId}-${i}`}
                      block={b}
                      index={i + 1}
                      onGraded={grade(it.sectionId)}
                    />
                  ))}
                </ul>

                {it.blocks.length === 0 && (
                  <p className="mt-3 text-[0.8rem] text-text-tertiary">
                    이 화면은 복습 문항을 만들지 못했습니다.
                  </p>
                )}
              </section>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
