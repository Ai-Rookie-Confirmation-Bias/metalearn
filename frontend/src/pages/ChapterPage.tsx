// [화면 2] 목차 하나 — 학습 순서와 왜 이렇게 나왔는지.
//
// 화면(슬라이스)마다 붙는 ⚡는 **규칙이 만든 문장 그대로**다. 단순 자르기에는
// reason이 비어 있어 ⚡가 안 뜬다. plan·tie_in처럼 실제로 바뀐 것만 표시한다.
//
// 채점은 여기서 안 한다 — 화면 상세에서 실제로 꺼내보고 그 결과가 올라온다.
import { Link, useParams } from "react-router-dom";
import { clsx } from "clsx";

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
          <h1 className="text-2xl font-bold text-text-primary">
            {data.inserted ? "✚" : "📘"} {data.title}
          </h1>
          <ModeBadge mode={data.mode} />
        </div>
        {/* 교재에 없던 단원이면 먼저 밝힌다. 원문(📎)이 없는 이유이기도 하다.

            책장에 그 내용을 이미 가르치는 자료가 있으면 **말이 달라진다** —
            "AI가 새로 썼습니다"가 아니라 "그 책 어디에 있습니다"다. 그 차이가
            학습자에게 크고, 그래서 문구를 통째로 가른다. */}
        {data.inserted &&
          (data.coveredBy ? (
            <p className="mt-2 rounded-lg bg-emerald-50 px-4 py-2.5 text-[0.83rem] text-text-secondary">
              <strong className="text-emerald-700">📚 책장에 있는 내용</strong> —
              진단에서 모른다고 하신 내용인데, <strong>이미 가지고 계신 자료</strong>에
              같은 개념이 있어 먼저 짚어 드립니다.
              <span className="mt-1 block font-medium text-emerald-800">
                {data.coveredBy}
              </span>
            </p>
          ) : (
            <p className="mt-2 rounded-lg bg-accent/5 px-4 py-2.5 text-[0.83rem] text-text-secondary">
              <strong className="text-accent">✚ 보강 개념</strong> — 진단에서
              모른다고 하신 내용이라 <strong>교재에는 없습니다.</strong> 여기 설명은
              교재 원문이 아니라 새로 쓴 것이라 📎 원문이 붙지 않습니다.
            </p>
          ))}
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
          <li
            key={s.sectionId}
            className={clsx(
              "rounded-lg border p-4",
              // 보충 화면은 교재에 원래 있던 화면이 아니다. 같은 모양으로 두면
              // 원문이라고 오해한다 — 왜 여기 있는지는 아래 reason이 말한다.
              s.inserted
                ? "border-violet-300 bg-violet-50/40"
                : "border-border-primary",
            )}
          >
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="text-[0.7rem] font-semibold text-text-tertiary">
                  {s.inserted ? (
                    <span className="text-violet-700">↻ 보충 화면 · 진도에 안 들어갑니다</span>
                  ) : (
                    <>{s.order + 1}번째 화면</>
                  )}
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

        {/* 목차의 **마지막 항목**은 언제나 단원 평가다. 커리큘럼이 만들어지는
            순간부터 자리를 잡고 있어야 "이 단원은 여기서 끝난다"가 보인다 —
            끝이 안 보이면 화면이 몇 개 남았는지만 세게 된다.

            🔒 **잠기는 건 여기뿐이다.** 학습 화면은 순서와 무관하게 언제나
            열려 있다(integration 목업은 안 배운 강의에 `cursor-not-allowed`를
            걸어뒀는데, 그쪽이 학습을 잠갔다가 이탈을 겪은 자리다).
            잠겨 있어도 **보여준다** — 무엇을 향해 가는지가 진도의 의미다. */}
        <li
          className={[
            "rounded-lg border-2 border-dashed p-4",
            data.formativeReady ? "border-accent bg-accent/5" : "border-border-primary",
          ].join(" ")}
        >
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="text-[0.7rem] font-semibold text-text-tertiary">
                마지막 — 단원 마무리
              </p>
              <p className="font-semibold text-text-primary">
                {data.formativeReady ? "📝" : "🔒"} 단원 평가
              </p>
            </div>
            {!data.formativeReady && (
              <span className="flex-shrink-0 text-[0.7rem] font-semibold text-text-tertiary">
                잠김
              </span>
            )}
          </div>

          <p className="mt-2 text-[0.8rem] text-text-secondary">
            여기까지 배운 것들을 <strong>섞어서</strong> 묻습니다. 하나씩은 알아도 같이
            놓으면 헷갈리는 지점을 찾습니다.
          </p>

          <div className="mt-3 border-t border-border-primary pt-3">
            {data.formativeReady ? (
              <Link
                to={`/curriculum/${encodeURIComponent(docId)}/chapters/${chapterIndex}/formative`}
                className="inline-block rounded bg-primary px-3 py-1.5 text-[0.8rem] font-medium text-white hover:bg-primary-hover"
              >
                평가 시작하기 →
              </Link>
            ) : (
              // 잠금 사유는 여기서도 말한다. 눌러야 알 수 있으면 잠김이 벌처럼
              // 보인다. 문장은 백엔드가 만든 것을 그대로 싣는다.
              <p className="text-[0.8rem] text-text-tertiary">
                {data.formativeReason} · 지금{" "}
                <strong className="text-text-secondary">{pct(data.progress)}</strong>
              </p>
            )}
          </div>
        </li>
      </ol>
    </div>
  );
}
