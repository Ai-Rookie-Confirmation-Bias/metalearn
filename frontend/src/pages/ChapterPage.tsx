// [화면 2] 목차 하나 — 학습 순서와 왜 이렇게 나왔는지.
//
// 화면(슬라이스)마다 붙는 ⚡는 **규칙이 만든 문장 그대로**다. 단순 자르기에는
// reason이 비어 있어 ⚡가 안 뜬다. plan·tie_in처럼 실제로 바뀐 것만 표시한다.
//
// 채점은 여기서 안 한다 — 화면 상세에서 실제로 꺼내보고 그 결과가 올라온다.
import { Link, useParams } from "react-router-dom";

import { Bar, ModeBadge, Reason, StatusBadge, pct } from "@/features/curriculum/components/bits";
import { useChapter } from "@/features/curriculum/queries/useCurriculum";

export function ChapterPage() {
  const { docId = "", index = "0" } = useParams<{ docId: string; index: string }>();
  const chapterIndex = Number(index);
  const { data, isLoading, isError } = useChapter(docId, chapterIndex);

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
          화면 {data.sections.length}개{data.pages && <> · 📖 {data.pages}</>}
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
                <p className="text-[0.7rem] font-semibold text-text-tertiary">
                  {s.order + 1}번째 화면
                </p>
                <p className="font-semibold text-text-primary">{s.title}</p>
                <p className="mt-0.5 text-[0.75rem] text-text-tertiary">
                  개념 {s.concepts.length}개{s.page && <> · 📖 {s.page}</>}
                  {s.attempts > 0 && <> · {s.attempts}문제 풀이</>}
                </p>
              </div>
              <div className="flex flex-shrink-0 items-center gap-1.5">
                {/* 맞힌 적 있는데 잊혀가는 화면. 아직 못 맞힌 건 여기가 아니라
                    상태 배지(약함/학습 중)가 잡는다 — 처방이 다르다. */}
                {s.needsReview && (
                  <span className="text-[0.7rem] font-semibold text-amber-700">🔁 복습</span>
                )}
                {s.improving && (
                  <span className="text-[0.7rem] font-semibold text-emerald-600">↗ 나아짐</span>
                )}
                <StatusBadge status={s.status} label={s.statusLabel} />
              </div>
            </div>

            {/* 화면 제목은 대표 개념 이름을 그대로 쓰는 일이 많다.
                라벨 없이 나열하면 제목과 개념이 구분이 안 된다. */}
            <div className="mt-2">
              <p className="text-[0.7rem] font-semibold text-text-tertiary">
                이 화면에서 배우는 개념
              </p>
              <p className="mt-0.5 text-[0.8rem] text-text-secondary">
                {s.concepts.map((c, i) => (
                  <span key={c}>
                    {i > 0 && " · "}
                    <span className={c === s.title ? "font-semibold text-text-primary" : ""}>
                      {c}
                    </span>
                  </span>
                ))}
              </p>
            </div>

            <div className="mt-2">
              <Reason text={s.reason} />
            </div>

            {s.weakConcepts.length > 0 && (
              <p className="mt-1 text-[0.8rem] text-red-600">
                🔴 자주 틀림: {s.weakConcepts.join(", ")}
              </p>
            )}

            <div className="mt-3 border-t border-border-primary pt-3">
              <Link
                to={`/curriculum/${encodeURIComponent(docId)}/sections/${s.sectionId}`}
                className="inline-block rounded bg-primary px-3 py-1.5 text-[0.8rem] font-medium text-white hover:bg-primary-hover"
              >
                {s.attempts > 0 ? "다시 보기" : "학습하기"} →
              </Link>
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}
