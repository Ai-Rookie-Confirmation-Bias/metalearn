// 진단 리포트 — **확정된 목차가 주인공**이다.
//
// 진단을 막 끝낸 사람이 알고 싶은 건 "무슨 순서로 배우게 되나"이고, 그 다음이
// "왜 그렇게 됐나"다. 그래서 목차를 세로로 세워 놓고 각 줄에 근거를 붙인다.
//
// ## 화면이 읽히는 순서
//
//     ① 숫자 셋      확인 32 → 모름 28 → 채운 단원 4   (인과가 화살표로)
//     ② 목차 타임라인  ✚ 보강은 강조, 교재 목차는 차분하게
//     ③ 성향 카드     목차와 달리 **앞으로 계속** 적용되는 것
//
// ③을 따로 뗀 이유가 있다. 목차는 여기서 확정되고 끝이지만 설명 방식은 계속
// 쓰인다. 한 상자에 두면 "목차는 안 바뀐다"는 말이 흐려진다.
//
// 근거는 두 겹으로 쓴다 — "문항에서 틀림"(확인된 것)과 "모른다고 답함"(자기
// 신고)은 무게가 다르고, 그 차이가 보여야 ✚가 임의로 붙은 게 아니게 된다.
import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { fetchSetup, type PrereqSubject } from "@/features/diagnostic/api";
import { getCourse } from "@/features/course/api";

const GOAL_LABEL: Record<string, string> = {
  exam: "시험 준비",
  work: "실무에 쓰려고",
  interest: "관심 있어서",
};

const STYLE_LABEL: Record<string, { name: string; effect: string }> = {
  metaphor: { name: "비유로", effect: "일상 비유를 정의보다 먼저 놓습니다" },
  definition: { name: "정의와 형식부터", effect: "정의를 먼저 제시하고 비유는 넣지 않습니다" },
  table: { name: "표로", effect: "비교되는 것은 표로 정리합니다" },
  why: { name: "왜 그런지까지", effect: "결론뿐 아니라 이유와 한계를 함께 씁니다" },
};

/** 목적격 조사 — 받침이 있으면 "을", 없으면 "를".
 *
 * `을(를)`은 개념 이름마다 괄호가 붙어 읽기가 거칠다. 한글 음절이 아니면
 * "를"로 둔다 — "TCP/IP 모델"처럼 섞인 이름이 흔하다.
 */
function objectParticle(word: string): string {
  const code = word.trim().slice(-1).charCodeAt(0);
  if (code < 0xac00 || code > 0xd7a3) return "를";
  return (code - 0xac00) % 28 ? "을" : "를";
}

function statOf(s: PrereqSubject) {
  return {
    failed: s.items.filter((i) => i.verified === false).map((i) => i.item),
    unknown: s.items.filter((i) => i.known === "unknown").length,
    known: s.items.filter((i) => i.known === "known").length,
  };
}

function Stat({
  n,
  label,
  tone,
}: {
  n: number;
  label: string;
  tone?: "accent" | "muted";
}) {
  return (
    <div className="min-w-0">
      <p
        className={
          tone === "accent"
            ? "text-[2rem] font-extrabold leading-none text-accent"
            : "text-[2rem] font-extrabold leading-none text-text-primary"
        }
      >
        {n}
      </p>
      <p className="mt-1.5 text-[0.75rem] font-medium text-text-tertiary">{label}</p>
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
  const unknown = subjects.reduce((n, s) => n + statOf(s).unknown, 0);

  const topics = [...(course?.topics ?? [])].sort((a, b) => a.seq - b.seq);
  const inserted = topics.filter((t) => t.origin === "inserted");
  const original = topics.filter((t) => t.origin !== "inserted");

  // 보강 단원 제목 = 과목명. 이걸로 목차 줄과 진단 결과를 잇는다.
  const byName = new Map(subjects.map((s) => [s.subject, s]));
  const addedNames = new Set(inserted.map((t) => t.title));
  // 물어봤지만 단원이 안 된 과목 = 충분히 안다고 나온 것. **뺀 것도 보여준다** —
  // 넣은 것만 보이면 "왜 이것만?"이 남는다.
  const skipped = subjects.filter((s) => !addedNames.has(s.subject));

  const style = setup.style ? STYLE_LABEL[setup.style] : undefined;
  const urgent =
    setup.goal === "exam" && setup.deadline_weeks != null && setup.deadline_weeks <= 2;

  return (
    <div className="mx-auto max-w-3xl px-8 pb-16 pt-8">
      <p className="text-[0.75rem] font-semibold tracking-wide text-accent">
        진단 완료
      </p>
      <h1 className="mt-1 text-[1.75rem] font-extrabold tracking-tight text-text-primary">
        {setup.documents[0] ?? "학습 자료"}
      </h1>
      <p className="mt-1 text-[0.85rem] text-text-secondary">
        답해주신 것으로 배울 순서를 정했어요.
      </p>

      {/* ① 숫자 셋 — 인과를 화살표로 잇는다 */}
      <div className="mt-7 flex items-start gap-6 rounded-2xl border border-border-primary bg-white px-7 py-6">
        <Stat n={total} label="확인한 선수 지식" />
        <span className="mt-2 text-[1.1rem] text-text-tertiary">→</span>
        <Stat n={unknown} label="모른다고 하신 것" />
        <span className="mt-2 text-[1.1rem] text-text-tertiary">→</span>
        <Stat n={inserted.length} label="먼저 채운 단원" tone="accent" />
      </div>

      {/* ② 목차 — 각 줄이 곧 결과다 */}
      <h2 className="mt-10 text-[1.05rem] font-bold text-text-primary">
        이 순서로 배우게 됩니다
      </h2>
      <p className="mt-1 text-[0.83rem] text-text-secondary">
        총 {topics.length}개 단원 · 앞의 {inserted.length}개는 진단에서 채운 것입니다.
      </p>

      <ol className="mt-4 space-y-2.5">
        {inserted.map((t, i) => {
          const s = byName.get(t.title);
          const st = s && statOf(s);
          return (
            <li
              key={t.id}
              className="rounded-xl border border-accent/25 bg-accent/[0.04] px-5 py-4"
            >
              <div className="flex items-center gap-2.5">
                <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-accent text-[0.72rem] font-bold text-white">
                  {i + 1}
                </span>
                <span className="font-bold text-text-primary">{t.title}</span>
                <span className="rounded bg-accent/15 px-1.5 py-0.5 text-[0.65rem] font-bold text-accent">
                  먼저 채움
                </span>
              </div>

              {st && (
                <div className="mt-2.5 space-y-1.5 pl-[2.1rem]">
                  {st.failed.length > 0 && (
                    <p className="text-[0.82rem] leading-relaxed text-text-secondary">
                      <span className="font-semibold text-red-700">문항에서 틀림</span>
                      {" — "}
                      {st.failed.join(" · ")}
                      {objectParticle(st.failed.join(" · "))} 못 맞히셨어요.
                    </p>
                  )}
                  {st.unknown > 0 && (
                    <p className="text-[0.82rem] leading-relaxed text-text-secondary">
                      <span className="font-semibold">모른다고 답함</span> —{" "}
                      {st.unknown}가지
                      {st.known > 0 && (
                        <span className="text-text-tertiary">
                          {" "}
                          (아는 것 {st.known}가지는 빼고 씁니다)
                        </span>
                      )}
                    </p>
                  )}
                </div>
              )}
            </li>
          );
        })}

        {original.map((t, i) => (
          <li
            key={t.id}
            className="flex items-center gap-2.5 rounded-xl border border-border-primary px-5 py-3"
          >
            <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-bg-secondary text-[0.72rem] font-bold text-text-tertiary">
              {inserted.length + i + 1}
            </span>
            <span className="text-[0.92rem] text-text-secondary">{t.title}</span>
            {i === 0 && (
              <span className="ml-auto text-[0.7rem] text-text-tertiary">
                여기부터 교재 목차
              </span>
            )}
          </li>
        ))}
      </ol>

      {skipped.length > 0 && (
        <p className="mt-4 rounded-xl bg-bg-secondary px-5 py-3.5 text-[0.82rem] leading-relaxed text-text-secondary">
          <strong className="text-text-primary">{skipped.length}과목</strong>은 이미
          아셔서 단원을 넣지 않았어요 — {skipped.map((s) => s.subject).join(" · ")}
        </p>
      )}

      {/* ③ 성향 — 목차와 수명이 다르다 */}
      <div className="mt-10 rounded-2xl bg-text-primary px-7 py-6 text-white">
        <p className="text-[0.72rem] font-semibold tracking-wide text-white/50">
          앞으로 계속 적용됩니다
        </p>
        <h2 className="mt-1 text-[1.05rem] font-bold">설명은 이렇게 씁니다</h2>

        <div className="mt-5 grid gap-5 sm:grid-cols-2">
          <div>
            <p className="text-[0.72rem] text-white/50">왜 배우나</p>
            <p className="mt-1 text-[1.05rem] font-bold">
              {setup.goal ? GOAL_LABEL[setup.goal] : "고르지 않음"}
              {setup.deadline_weeks != null && (
                <span className="ml-1.5 text-[0.85rem] font-medium text-white/60">
                  {setup.deadline_weeks}주 남음
                </span>
              )}
            </p>
            {/* ⚠️ 문턱(2주)이 백엔드 `planner.URGENT_WEEKS`에도 있다. 거기를
                고치면 여기도 같이 고쳐야 한다. "시험인데 왜 안 줄이지"가
                화면에서 바로 풀리도록 이유까지 적는다. */}
            <p className="mt-1.5 text-[0.82rem] leading-relaxed text-white/70">
              {setup.goal === "exam"
                ? urgent
                  ? "시간이 얼마 없어 핵심만 짧게 씁니다."
                  : "기한이 넉넉해서 범위를 빠뜨리지 않도록 표준 분량으로 씁니다."
                : setup.goal === "work"
                  ? "실무에 쓰시려는 자료라 왜 그런지까지 함께 씁니다."
                  : setup.goal === "interest"
                    ? "부담 없이 훑는 자료라 핵심만 보여드립니다."
                    : "표준 분량으로 씁니다."}
            </p>
          </div>

          <div>
            <p className="text-[0.72rem] text-white/50">어떤 설명이 편한가</p>
            <p className="mt-1 text-[1.05rem] font-bold">
              {style?.name ?? "고르지 않음"}
            </p>
            <p className="mt-1.5 text-[0.82rem] leading-relaxed text-white/70">
              {style?.effect ?? "기본 형식으로 씁니다."}
            </p>
          </div>
        </div>

        <p className="mt-5 border-t border-white/15 pt-4 text-[0.8rem] leading-relaxed text-white/60">
          ⚡ 목차는 여기서 확정됐고 <strong className="text-white/90">더 바뀌지
          않습니다.</strong> 학습하며 약한 곳이 드러나면 단원을 새로 끼우는 대신 그
          목차의 설명을 늘리거나 줄입니다.
        </p>
      </div>

      <Link
        to={`/curriculum/${encodeURIComponent(docId)}`}
        className="mt-8 inline-flex w-full items-center justify-center rounded-xl bg-primary px-5 py-4 text-[0.95rem] font-bold text-white shadow-sm transition-all hover:bg-primary-hover hover:-translate-y-0.5 hover:shadow-md"
      >
        학습 시작하기
      </Link>
    </div>
  );
}
