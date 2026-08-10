// 진단 리포트 — **확정된 목차가 주인공**이다.
//
// 진단을 막 끝낸 사람이 알고 싶은 건 "무슨 순서로 배우게 되나"이고, 그 다음이
// "왜 그렇게 됐나"다. 그래서 목차를 그대로 세워 놓고 **각 줄에 근거를 붙인다.**
//
//     ✚ 데이터베이스 기초
//          배열과 리스트를 문항에서 틀리셨고, 9가지를 모른다고 하셨어요
//     ── 여기부터 교재 목차 ──
//     1. 소프트웨어 구축
//
// 과목별 결과를 먼저 늘어놓고 목차를 따로 그리면 같은 것을 두 번 읽게 된다.
// 목차 줄 자체가 결과가 되도록 합쳤다.
//
// 성향은 **맨 아래 따로** 뗀다. 목차는 여기서 확정되고 끝이지만 설명 방식은
// 앞으로 계속 적용되는 것이라, 같은 상자에 두면 둘의 수명이 뒤섞인다.
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
  definition: { name: "정의부터", effect: "정의와 형식을 먼저 제시합니다" },
  table: { name: "표로", effect: "비교되는 것은 표로 정리합니다" },
  why: { name: "왜부터", effect: "왜 그런지·어디서 나왔는지까지 씁니다" },
};

/** 목적격 조사. 받침이 있으면 "을", 없으면 "를".
 *
 * `을(를)`로 두면 개념 이름이 화면에 그대로 나오는 자리마다 괄호가 붙어
 * 읽기가 거칠어진다. 한글 음절이 아니면(영문·숫자로 끝나면) "를"로 둔다 —
 * "TCP/IP 모델"처럼 섞인 이름이 흔하다.
 */
function objectParticle(word: string): string {
  const last = word.trim().slice(-1);
  const code = last.charCodeAt(0);
  if (code < 0xac00 || code > 0xd7a3) return "를";
  return (code - 0xac00) % 28 ? "을" : "를";
}

/** 이 과목이 왜 단원이 됐는지 한 문장. 확인된 오답을 앞에 둔다. */
function reasonOf(s: PrereqSubject): string {
  const failed = s.items.filter((i) => i.verified === false).map((i) => i.item);
  const unknown = s.items.filter((i) => i.known === "unknown").length;
  const names = failed.join(" · ");
  const wrong = names && `${names}${objectParticle(names)} 문항에서 틀리셨`;

  if (failed.length && unknown) {
    return `${wrong}고, ${unknown}가지를 모른다고 하셨어요.`;
  }
  if (failed.length) return `${wrong}어요.`;
  if (unknown) return `${unknown}가지를 모른다고 하셨어요.`;
  return "확인이 더 필요해서 먼저 짚고 갑니다.";
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
  const topics = [...(course?.topics ?? [])].sort((a, b) => a.seq - b.seq);
  const inserted = topics.filter((t) => t.origin === "inserted");
  const original = topics.filter((t) => t.origin !== "inserted");

  // 보강 단원 제목 = 과목명. 이걸로 목차 줄과 진단 결과를 잇는다.
  const byName = new Map(subjects.map((s) => [s.subject, s]));
  // 물어봤지만 단원이 안 된 과목 = 충분히 안다고 나온 것. **뺀 것도 보여준다** —
  // 무엇을 넣었는지만 보이면 "왜 이것만?"이 남는다.
  const addedNames = new Set(inserted.map((t) => t.title));
  const skipped = subjects.filter((s) => !addedNames.has(s.subject));

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

      {/* ── 확정된 목차. 각 줄이 곧 결과다 ────────────────────────── */}
      <div className="mt-6 overflow-hidden rounded-2xl border border-border-primary bg-white">
        <div className="border-b border-border-primary bg-bg-secondary px-6 py-4">
          <h2 className="font-bold text-text-primary">이 순서로 배우게 됩니다</h2>
          <p className="mt-1 text-[0.83rem] text-text-secondary">
            먼저 채운 단원 <strong className="text-accent">{inserted.length}개</strong>
            {skipped.length > 0 && (
              <>
                {" "}
                · 아셔서 넣지 않은 과목 <strong>{skipped.length}개</strong>
              </>
            )}{" "}
            · 교재 목차 {original.length}개
          </p>
        </div>

        {inserted.map((t) => {
          const s = byName.get(t.title);
          return (
            <div
              key={t.id}
              className="border-b border-border-primary bg-accent/[0.03] px-6 py-4"
            >
              <div className="flex items-baseline gap-2">
                <span className="shrink-0 rounded bg-accent/15 px-1.5 py-0.5 text-[0.68rem] font-bold text-accent">
                  ✚ 먼저 채움
                </span>
                <span className="font-bold text-text-primary">{t.title}</span>
              </div>
              {s && (
                <p className="mt-1.5 text-[0.82rem] leading-relaxed text-text-secondary">
                  {reasonOf(s)}
                </p>
              )}
            </div>
          );
        })}

        {original.length > 0 && (
          <p className="border-b border-border-primary bg-bg-secondary px-6 py-2 text-[0.72rem] font-semibold tracking-wide text-text-tertiary">
            여기부터 교재 목차
          </p>
        )}
        {original.map((t) => (
          <div
            key={t.id}
            className="border-b border-border-primary px-6 py-3 text-[0.9rem] text-text-secondary last:border-b-0"
          >
            {t.title}
          </div>
        ))}
      </div>

      {/* 뺀 것 — 넣은 것만 보이면 "왜 이것만?"이 남는다 */}
      {skipped.length > 0 && (
        <div className="mt-4 rounded-xl border border-border-primary px-5 py-4">
          <p className="text-[0.8rem] font-semibold text-text-secondary">
            이건 아셔서 넣지 않았어요
          </p>
          <p className="mt-1.5 text-[0.82rem] leading-relaxed text-text-tertiary">
            {skipped.map((s) => s.subject).join(" · ")}
          </p>
        </div>
      )}

      {/* ── 성향은 따로. 목차와 수명이 다르다 ─────────────────────── */}
      <div className="mt-6 rounded-2xl border border-border-primary bg-white px-6 py-5">
        <h2 className="font-bold text-text-primary">설명은 이렇게 씁니다</h2>
        <p className="mt-0.5 text-[0.83rem] text-text-secondary">
          목차와 달리 이건 <strong>앞으로 계속</strong> 적용됩니다.
        </p>

        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          <div className="rounded-xl bg-bg-secondary px-4 py-3.5">
            <p className="text-[0.72rem] font-semibold text-text-tertiary">왜 배우나</p>
            <p className="mt-1 font-bold text-text-primary">
              {setup.goal ? GOAL_LABEL[setup.goal] : "고르지 않음"}
              {setup.deadline_weeks != null && (
                <span className="ml-1.5 text-[0.85rem] font-medium text-text-secondary">
                  · {setup.deadline_weeks}주 남음
                </span>
              )}
            </p>
            {/* ⚠️ 문턱(2주)이 백엔드 `planner.URGENT_WEEKS`에도 있다. 거기를
                고치면 여기도 같이 고쳐야 한다. "시험인데 왜 안 줄이지"가
                화면에서 바로 풀리도록 이유까지 적는다. */}
            <p className="mt-1.5 text-[0.8rem] leading-relaxed text-text-secondary">
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

          <div className="rounded-xl bg-bg-secondary px-4 py-3.5">
            <p className="text-[0.72rem] font-semibold text-text-tertiary">
              어떤 설명이 편한가
            </p>
            <p className="mt-1 font-bold text-text-primary">
              {style?.name ?? "고르지 않음"}
            </p>
            <p className="mt-1.5 text-[0.8rem] leading-relaxed text-text-secondary">
              {style?.effect ?? "기본 형식으로 씁니다."}
            </p>
          </div>
        </div>

        <p className="mt-4 text-[0.8rem] leading-relaxed text-text-tertiary">
          ⚡ 목차는 여기서 확정됐고 <strong className="text-text-secondary">더
          바뀌지 않습니다.</strong> 학습하며 약한 곳이 드러나면 단원을 새로 끼우는
          대신 그 목차의 설명을 늘리거나 줄입니다.
        </p>
      </div>

      <Link
        to={`/curriculum/${encodeURIComponent(docId)}`}
        className="mt-6 inline-flex w-full items-center justify-center rounded-xl bg-primary px-5 py-3.5 text-[0.95rem] font-semibold text-white shadow-sm transition-all hover:bg-primary-hover hover:-translate-y-0.5"
      >
        학습 시작하기
      </Link>
    </div>
  );
}
