// [화면 1] 내 자료 — 준비도와 목차 목록.
//
// 목차는 교재 그대로 두고 **분량과 상태만** 바뀐다. 목차가 사라지거나 새로 생기지
// 않는 게 요점이다 — 진단이 좋든 나쁘든 시험 범위는 교재 전체이고, 목차가 흔들리면
// 어디쯤 왔는지 감각이 사라진다.
import { Link, useParams } from "react-router-dom";

import { KIND_LABEL, type AttemptKind } from "@/features/curriculum/api/curriculum";
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

  // 준비도 = 이해도 × 진도 × 회상. 준비도만 낮고 이해도는 높으면 **잊은 것**이라
  // 처방이 "복습"이고, 둘 다 낮으면 아직 모르는 것이라 "다시 학습"이다.
  const forgotten = data.understanding - data.readiness;
  const kinds = Object.entries(data.byKind).filter(([, n]) => n > 0) as [
    AttemptKind,
    number,
  ][];

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

        {/* 이 숫자가 어디서 왔는지 — 진단·학습·복습·평가가 전부 여기로 모인다.
            근거를 안 보여주면 준비도가 그냥 떨어진 숫자로 보인다. */}
        {kinds.length > 0 && (
          <p className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[0.75rem] text-text-tertiary">
            {kinds.map(([k, n]) => (
              <span key={k}>
                {KIND_LABEL[k]} <span className="tabular-nums font-medium">{n}</span>
              </span>
            ))}
          </p>
        )}

        {/* 잊어서 낮은 것과 아직 몰라서 낮은 것은 처방이 다르다. */}
        {forgotten >= 0.05 && (
          <p className="mt-2 rounded-lg bg-amber-50/70 px-3 py-2 text-[0.8rem] text-amber-800">
            🔁 이해한 건 {pct(data.understanding)}인데 지금 꺼낼 수 있는 건{" "}
            {pct(data.readiness)}입니다. 복습이 필요한 절 {data.sectionsDue}개.
          </p>
        )}
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
                  {ch.sectionsDue > 0 && (
                    <span className="text-[0.7rem] font-semibold text-amber-700">
                      🔁 복습 {ch.sectionsDue}
                    </span>
                  )}
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
