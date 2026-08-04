// [화면 2] 목차 하나 — 학습 순서와 왜 이렇게 나왔는지.
//
// 절마다 붙는 ⚡는 **규칙이 만든 문장 그대로**다("교재가 이 6개를 같은 표에 묶어
// 설명합니다"). 판단을 LLM이 했다면 못 쓰는 문장이고, 이게 화면에 보이는 게
// "AI가 내 커리큘럼을 만들었다"를 느끼게 하는 지점이다.
//
// 맞음/틀림 버튼은 임시다 — 학습 화면(절 상세)이 붙기 전까지 루프를 눈으로
// 확인하려고 둔다. 누르면 목차 분량과 준비도가 그 자리에서 바뀐다.
import { Link, useParams } from "react-router-dom";

import { Bar, ModeBadge, Reason, StatusBadge, pct } from "@/features/curriculum/components/bits";
import { useAnswer, useChapter } from "@/features/curriculum/queries/useCurriculum";

export function ChapterPage() {
  const { docId = "", index = "0" } = useParams<{ docId: string; index: string }>();
  const chapterIndex = Number(index);
  const { data, isLoading, isError } = useChapter(docId, chapterIndex);
  const answer = useAnswer(docId);

  if (isLoading) return <p className="p-8 text-text-secondary">불러오는 중…</p>;
  if (isError || !data) return <p className="p-8 text-red-600">목차를 불러오지 못했습니다.</p>;

  return (
    <div className="mx-auto max-w-3xl p-8">
      <Link
        to={`/curriculum/${encodeURIComponent(docId)}`}
        className="text-[0.8rem] text-text-tertiary hover:underline"
      >
        ← {data.docTitle}
      </Link>

      <header className="mt-3 mb-6 border-b border-border-primary pb-6">
        <div className="flex items-start justify-between gap-3">
          <h1 className="text-2xl font-bold text-text-primary">📘 {data.title}</h1>
          <ModeBadge mode={data.mode} />
        </div>
        <p className="mt-1 text-[0.8rem] text-text-tertiary">
          절 {data.sections.length}개{data.pages && <> · 📖 {data.pages}</>}
        </p>

        <div className="mt-4 flex gap-8">
          <div>
            <p className="text-[0.75rem] text-text-tertiary">이 단원 이해도</p>
            <p className="text-xl font-bold tabular-nums text-text-primary">{pct(data.ratio)}</p>
          </div>
          <div>
            <p className="text-[0.75rem] text-text-tertiary">전체 준비도</p>
            <p className="text-xl font-bold tabular-nums text-text-primary">
              {pct(data.readiness)}
            </p>
          </div>
        </div>
        <div className="mt-3">
          <Bar value={data.progress} tone="accent" />
        </div>

        {data.reason && (
          <div className="mt-4 rounded-lg bg-indigo-50/60 px-3 py-2">
            <Reason text={data.reason} />
          </div>
        )}
      </header>

      <h2 className="mb-3 text-sm font-bold text-text-secondary">다음 학습 순서</h2>
      <ol className="space-y-3">
        {data.sections.map((s) => (
          <li key={s.sectionId} className="rounded-lg border border-border-primary p-4">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="font-semibold text-text-primary">
                  <span className="mr-1.5 tabular-nums text-text-tertiary">{s.order + 1}.</span>
                  {s.title}
                </p>
                <p className="mt-1 text-[0.75rem] text-text-tertiary">
                  개념 {s.concepts.length}개{s.page && <> · 📖 {s.page}</>}
                  {s.attempts > 0 && <> · {s.attempts}문제 풀이</>}
                </p>
              </div>
              <div className="flex flex-shrink-0 items-center gap-1.5">
                {s.improving && (
                  <span className="text-[0.7rem] font-semibold text-emerald-600">↗ 나아짐</span>
                )}
                <StatusBadge status={s.status} label={s.statusLabel} />
              </div>
            </div>

            <p className="mt-2 text-[0.8rem] text-text-secondary">{s.concepts.join(" · ")}</p>

            <div className="mt-2">
              <Reason text={s.reason} />
            </div>

            {s.weakConcepts.length > 0 && (
              <p className="mt-1 text-[0.8rem] text-red-600">
                🔴 자주 틀림: {s.weakConcepts.join(", ")}
              </p>
            )}

            {/* 임시 — 절 상세 화면이 붙으면 사라진다 */}
            <div className="mt-3 flex gap-2 border-t border-border-primary pt-3">
              <button
                type="button"
                disabled={answer.isPending}
                onClick={() =>
                  answer.mutate({
                    sectionId: s.sectionId,
                    correct: true,
                    conceptKey: s.concepts[0],
                  })
                }
                className="rounded border border-border-primary px-2.5 py-1 text-[0.75rem] hover:bg-bg-secondary disabled:opacity-50"
              >
                맞음
              </button>
              <button
                type="button"
                disabled={answer.isPending}
                onClick={() =>
                  answer.mutate({
                    sectionId: s.sectionId,
                    correct: false,
                    conceptKey: s.concepts[0],
                  })
                }
                className="rounded border border-border-primary px-2.5 py-1 text-[0.75rem] hover:bg-bg-secondary disabled:opacity-50"
              >
                틀림
              </button>
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}
