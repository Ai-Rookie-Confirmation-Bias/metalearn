// 진단 리포트 — **왜 이 목차가 됐는지**를 한 화면에 편다.
//
// 진단을 막 끝낸 사람이 보고 싶은 건 진도 0%짜리 목차 목록이 아니라 "내가 뭘
// 답했고 그래서 뭐가 바뀌었나"다. 그래서 진단 직후 자리를 이 화면이 받는다.
//
// 위에서 아래로 읽으면 인과가 이어지도록 넷으로 짰다:
//
//     ① 한 줄 결론      선수 N개 중 M개를 모른다 → 단원 K개가 붙었다
//     ② 무엇을 물었나    과목별로. **자기 신고와 확인된 오답을 갈라 쓴다**
//     ③ 그래서 목차가    ✚ 보강 단원 + 교재 목차
//     ④ 설명은 이렇게    목표·기한·형식이 분량과 문체를 정한다
//
// ②가 이 화면의 본론이다. 지금까지 보강 단원이 왜 생겼는지는 `note`에만 있고
// 화면에 없었다 — ✚ 배지가 임의로 붙은 게 아니라는 근거가 여기서 나온다.
import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { fetchSetup, type PrereqSubject } from "@/features/diagnostic/api";
import { getCourse } from "@/features/course/api";

const GOAL_LABEL: Record<string, string> = {
  exam: "시험 준비",
  work: "실무에 쓰려고",
  interest: "관심 있어서",
};

// 형식이 설명을 어떻게 바꾸는지까지 적는다. 고른 것만 보여주면 "그래서 뭐가
// 달라지나"를 학습자가 알 수 없다.
const STYLE_LABEL: Record<string, { name: string; effect: string }> = {
  metaphor: { name: "비유로", effect: "일상 비유를 정의보다 먼저 놓습니다" },
  definition: { name: "정의부터", effect: "정의와 형식을 먼저 제시합니다" },
  table: { name: "표로", effect: "비교되는 것은 표로 정리합니다" },
  why: { name: "왜부터", effect: "왜 그런지·어디서 나왔는지까지 씁니다" },
};

type Counts = { known: number; unknown: number; asked: number; wrong: number };

function count(subject: PrereqSubject): Counts {
  return {
    known: subject.items.filter((i) => i.known === "known").length,
    unknown: subject.items.filter((i) => i.known === "unknown").length,
    asked: subject.items.filter((i) => i.verified !== null).length,
    wrong: subject.items.filter((i) => i.verified === false).length,
  };
}

function SubjectCard({ subject }: { subject: PrereqSubject }) {
  const c = count(subject);
  // 문항에서 틀린 것 = 확인된 결손. 자기 신고보다 근거가 세다.
  const confirmed = subject.items.filter((i) => i.verified === false);
  const declared = subject.items.filter(
    (i) => i.known === "unknown" && i.verified !== false,
  );
  const known = subject.items.filter((i) => i.known === "known");

  return (
    <div className="rounded-xl border border-border-primary bg-white p-5">
      <div className="mb-3 flex items-baseline justify-between gap-3">
        <h3 className="font-bold text-text-primary">{subject.subject}</h3>
        <span className="shrink-0 text-[0.78rem] text-text-tertiary">
          안다 {c.known} · 모른다 {c.unknown}
          {c.asked > 0 && <> · 확인 문항 {c.asked}</>}
        </span>
      </div>

      {confirmed.length > 0 && (
        <div className="mb-3">
          <p className="mb-1.5 text-[0.75rem] font-semibold text-red-700">
            🔴 문항에서 틀리셨어요
          </p>
          <div className="flex flex-wrap gap-1.5">
            {confirmed.map((i) => (
              <span
                key={i.id}
                className="rounded-md bg-red-50 px-2 py-1 text-[0.75rem] font-medium text-red-700"
              >
                {i.item}
              </span>
            ))}
          </div>
        </div>
      )}

      {declared.length > 0 && (
        <div className="mb-3">
          <p className="mb-1.5 text-[0.75rem] font-semibold text-text-secondary">
            모른다고 답하셨어요
          </p>
          <div className="flex flex-wrap gap-1.5">
            {declared.map((i) => (
              <span
                key={i.id}
                className="rounded-md bg-bg-secondary px-2 py-1 text-[0.75rem] text-text-secondary"
              >
                {i.item}
              </span>
            ))}
          </div>
        </div>
      )}

      {known.length > 0 && (
        <p className="text-[0.75rem] text-text-tertiary">
          이미 아는 것 — {known.map((i) => i.item).join(" · ")}
        </p>
      )}
    </div>
  );
}

export function DiagnosticReportPage() {
  const { docId = "" } = useParams();

  // 자료 id = 코스 id다(커리큘럼이 코스를 같은 키로 든다).
  const { data: setup, isLoading, isError } = useQuery({
    queryKey: ["diagnostic", "setup", docId],
    queryFn: () => fetchSetup(docId),
    enabled: Boolean(docId),
  });
  const { data: course } = useQuery({
    queryKey: ["course", docId],
    queryFn: () => getCourse(docId),
    enabled: Boolean(docId),
  });

  if (isLoading) return <p className="p-8 text-text-secondary">불러오는 중…</p>;
  if (isError || !setup)
    return <p className="p-8 text-red-600">진단 결과를 불러오지 못했습니다.</p>;

  const subjects = setup.subjects;
  const total = subjects.reduce((n, s) => n + s.items.length, 0);
  const unknown = subjects.reduce((n, s) => n + count(s).unknown, 0);
  const wrong = subjects.reduce((n, s) => n + count(s).wrong, 0);

  const topics = course?.topics ?? [];
  const inserted = topics.filter((t) => t.origin === "inserted");
  const original = topics.filter((t) => t.origin !== "inserted");
  const style = setup.style ? STYLE_LABEL[setup.style] : undefined;

  return (
    <div className="mx-auto max-w-3xl p-8">
      <Link
        to={`/curriculum/${encodeURIComponent(docId)}`}
        className="text-[0.8rem] text-text-tertiary hover:underline"
      >
        ← 자료 개요
      </Link>

      <h1 className="mt-3 text-2xl font-bold text-text-primary">진단 리포트</h1>
      <p className="mt-1 text-[0.85rem] text-text-secondary">
        {setup.documents.join(" · ")}
      </p>

      {/* ① 한 줄 결론 */}
      <section className="mt-6 rounded-xl bg-accent/5 p-5">
        <p className="text-[1.05rem] leading-relaxed text-text-primary">
          선수 지식 <strong>{total}개</strong>를 확인해서{" "}
          <strong>{unknown}개</strong>를 모른다고 하셨고
          {wrong > 0 && (
            <>
              , 그중 <strong>{wrong}개</strong>는 문항에서도 확인됐습니다
            </>
          )}
          . 그래서 <strong>{inserted.length}개 단원</strong>을 목차 앞에 채웠어요.
        </p>
      </section>

      {/* ② 무엇을 물었나 */}
      <section className="mt-8">
        <h2 className="mb-1 text-lg font-bold text-text-primary">무엇을 확인했나</h2>
        <p className="mb-4 text-[0.85rem] text-text-secondary">
          이 자료를 배우려면 먼저 알아야 하는 것들입니다.
        </p>
        <div className="space-y-3">
          {subjects.map((s) => (
            <SubjectCard key={s.subject} subject={s} />
          ))}
        </div>
      </section>

      {/* ③ 그래서 목차가 이렇게 됐다 */}
      {topics.length > 0 && (
        <section className="mt-8">
          <h2 className="mb-1 text-lg font-bold text-text-primary">
            그래서 목차가 이렇게 됐어요
          </h2>
          <p className="mb-4 text-[0.85rem] text-text-secondary">
            보강 {inserted.length}개 + 교재 목차 {original.length}개
          </p>

          <ol className="overflow-hidden rounded-xl border border-border-primary">
            {inserted.map((t) => (
              <li
                key={t.id}
                className="flex items-center gap-2 border-b border-border-primary bg-accent/5 px-4 py-3 text-[0.9rem]"
              >
                <span className="rounded bg-accent/15 px-1.5 py-0.5 text-[0.68rem] font-bold text-accent">
                  ✚ 새로 채움
                </span>
                <span className="font-medium text-text-primary">{t.title}</span>
              </li>
            ))}
            {original.map((t) => (
              <li
                key={t.id}
                className="border-b border-border-primary px-4 py-3 text-[0.9rem] text-text-secondary last:border-b-0"
              >
                {t.title}
              </li>
            ))}
          </ol>
        </section>
      )}

      {/* ④ 설명은 이렇게 씁니다 */}
      <section className="mt-8">
        <h2 className="mb-1 text-lg font-bold text-text-primary">
          설명은 이렇게 씁니다
        </h2>
        <p className="mb-4 text-[0.85rem] text-text-secondary">
          고르신 두 가지가 목차마다 분량과 문체를 정합니다.
        </p>

        <div className="grid gap-3 sm:grid-cols-2">
          <div className="rounded-xl border border-border-primary bg-white p-5">
            <p className="text-[0.75rem] font-semibold text-text-tertiary">왜 배우나</p>
            <p className="mt-1 font-bold text-text-primary">
              {setup.goal ? GOAL_LABEL[setup.goal] : "고르지 않음"}
              {setup.deadline_weeks != null && (
                <span className="ml-1.5 text-[0.85rem] font-medium text-text-secondary">
                  · {setup.deadline_weeks}주 남음
                </span>
              )}
            </p>
            {/* ⚠️ 문턱(2주)이 백엔드 `planner.URGENT_WEEKS`에도 있다. 규칙이
                두 곳에 생겼으니, 거기를 고치면 여기도 같이 고쳐야 한다.
                **기한이 넉넉한 시험을 표준으로 두는 이유까지** 적는다 —
                "시험인데 왜 안 줄이지"가 화면에서 바로 풀려야 한다. */}
            <p className="mt-2 text-[0.8rem] leading-relaxed text-text-secondary">
              {setup.goal === "exam"
                ? setup.deadline_weeks != null && setup.deadline_weeks <= 2
                  ? "시간이 얼마 없어 핵심만 짧게 씁니다."
                  : "기한이 넉넉해서 범위를 빠뜨리지 않도록 표준 분량으로 씁니다."
                : setup.goal === "work"
                  ? "실무에 쓰시려는 자료라 왜 그런지까지 함께 씁니다."
                  : setup.goal === "interest"
                    ? "부담 없이 훑는 자료라 핵심만 보여드립니다."
                    : "표준 분량으로 씁니다."}
            </p>
          </div>

          <div className="rounded-xl border border-border-primary bg-white p-5">
            <p className="text-[0.75rem] font-semibold text-text-tertiary">
              어떤 설명이 편한가
            </p>
            <p className="mt-1 font-bold text-text-primary">
              {style?.name ?? "고르지 않음"}
            </p>
            <p className="mt-2 text-[0.8rem] leading-relaxed text-text-secondary">
              {style?.effect ?? "기본 형식으로 씁니다."}
            </p>
          </div>
        </div>

        <p className="mt-4 rounded-lg bg-bg-secondary px-4 py-3 text-[0.8rem] leading-relaxed text-text-secondary">
          ⚡ 여기서부터 <strong className="text-text-primary">목차는 바뀌지 않습니다.</strong>{" "}
          학습하면서 약한 곳이 드러나면 단원을 새로 끼우는 대신 그 목차의 설명을
          늘리거나 줄입니다.
        </p>
      </section>

      <Link
        to={`/curriculum/${encodeURIComponent(docId)}`}
        className="mt-8 inline-flex w-full items-center justify-center rounded-xl bg-primary px-5 py-3.5 text-[0.95rem] font-semibold text-white shadow-sm transition-all hover:bg-primary-hover hover:-translate-y-0.5"
      >
        학습 시작하기
      </Link>
    </div>
  );
}
