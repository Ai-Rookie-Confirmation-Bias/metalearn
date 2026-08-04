// [화면 1] 내 자료 — 준비도와 목차 목록.
//
// 목차는 교재 그대로 두고 **분량과 상태만** 바뀐다. 목차가 사라지거나 새로 생기지
// 않는 게 요점이다 — 진단이 좋든 나쁘든 시험 범위는 교재 전체이고, 목차가 흔들리면
// 어디쯤 왔는지 감각이 사라진다.
import { Link, useParams } from "react-router-dom";

import { Bar, ModeBadge, Reason, StatusBadge, pct } from "@/features/curriculum/components/bits";
import { useDocument, useDocuments } from "@/features/curriculum/queries/useCurriculum";

function Picker() {
  const { data, isLoading } = useDocuments();
  if (isLoading) return <p className="p-8 text-text-secondary">불러오는 중…</p>;
  if (!data?.length)
    return (
      <p className="p-8 text-text-secondary">
        올린 자료가 없습니다. 백엔드 <code>tests/fixtures</code>에 파싱 결과 md를 넣어주세요.
      </p>
    );
  return (
    <div className="mx-auto max-w-3xl p-8">
      <h1 className="mb-6 text-xl font-bold text-text-primary">내 자료</h1>
      <ul className="space-y-2">
        {data.map((id) => (
          <li key={id}>
            <Link
              to={`/curriculum/${encodeURIComponent(id)}`}
              className="block rounded-lg border border-border-primary px-4 py-3 font-medium hover:bg-bg-secondary"
            >
              📚 {id}
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function CurriculumPage() {
  const { docId } = useParams<{ docId: string }>();
  const { data, isLoading, isError } = useDocument(docId);

  if (!docId) return <Picker />;
  if (isLoading) return <p className="p-8 text-text-secondary">불러오는 중…</p>;
  if (isError || !data) return <p className="p-8 text-red-600">자료를 불러오지 못했습니다.</p>;

  const hours = Math.floor(data.estimatedMinutes / 60);
  const mins = data.estimatedMinutes % 60;

  return (
    <div className="mx-auto max-w-3xl p-8">
      <Link to="/curriculum" className="text-[0.8rem] text-text-tertiary hover:underline">
        ← 내 자료
      </Link>

      <header className="mt-3 mb-8">
        <h1 className="text-2xl font-bold text-text-primary">📚 {data.title}</h1>
        <div className="mt-4 flex items-baseline gap-2">
          <span className="text-3xl font-bold tabular-nums text-text-primary">
            {pct(data.readiness)}
          </span>
          <span className="text-sm text-text-secondary">준비도</span>
        </div>
        <div className="mt-2">
          <Bar value={data.readiness} />
        </div>
        <p className="mt-2 text-[0.8rem] text-text-tertiary">
          남은 절 {data.remainingSections} / {data.sectionsTotal} · 예상{" "}
          {hours > 0 ? `${hours}시간 ` : ""}
          {mins}분
        </p>
      </header>

      <ul className="space-y-3">
        {data.chapters.map((ch) => (
          <li key={ch.index}>
            <Link
              to={`/curriculum/${encodeURIComponent(data.docId)}/chapters/${ch.index}`}
              className="block rounded-lg border border-border-primary p-4 transition-colors hover:bg-bg-secondary"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="truncate font-semibold text-text-primary">{ch.title}</p>
                  <p className="mt-0.5 text-[0.75rem] text-text-tertiary">
                    절 {ch.sectionsDone}/{ch.sectionsTotal}
                    {ch.pages && <> · 📖 {ch.pages}</>}
                  </p>
                </div>
                <div className="flex flex-shrink-0 items-center gap-1.5">
                  {data.weakestChapter === ch.index && (
                    <span className="text-[0.7rem] font-semibold text-red-600">🔴 가장 약함</span>
                  )}
                  <ModeBadge mode={ch.mode} />
                  <StatusBadge status={ch.status} label={ch.statusLabel} />
                </div>
              </div>

              <div className="mt-3">
                <Bar value={ch.progress} tone="accent" />
              </div>

              {ch.reason && (
                <div className="mt-2">
                  <Reason text={ch.reason} />
                </div>
              )}
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
