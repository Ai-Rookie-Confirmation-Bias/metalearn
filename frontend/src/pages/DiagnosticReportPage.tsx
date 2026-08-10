// 진단 리포트 — **왜 이 목차가 됐는지**를 한 화면에 편다.
//
// 진단을 막 끝낸 사람이 보고 싶은 건 진도 0%짜리 목차 목록이 아니라 "내가 뭘
// 답했고 그래서 뭐가 바뀌었나"다. 그래서 진단 직후 자리를 이 화면이 받는다.
//
// ## 한 박스에 몰아 넣는다
//
// 처음엔 과목마다 카드를 나눴는데, 그러면 **인과가 끊긴다.** "이걸 틀렸다"와
// "그래서 이 단원이 생겼다"가 다른 상자에 있으면 두 사실이 이어져 보이지 않는다.
// 한 박스 안에서 줄만 그어 나누고, 과목마다 마지막 줄이 결과(→ ✚)가 되게 했다.
//
// 자기 신고와 확인된 오답은 갈라 쓴다. "모른다고 답하셨어요"와 "문항에서
// 틀리셨어요"는 근거의 무게가 다르고, 그 차이가 보여야 ✚ 배지가 임의로 붙은
// 게 아니라는 게 드러난다.
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

function counts(s: PrereqSubject) {
  return {
    known: s.items.filter((i) => i.known === "known").length,
    unknown: s.items.filter((i) => i.known === "unknown").length,
    asked: s.items.filter((i) => i.verified !== null).length,
    wrong: s.items.filter((i) => i.verified === false).length,
  };
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
  const unknown = subjects.reduce((n, s) => n + counts(s).unknown, 0);
  const asked = subjects.reduce((n, s) => n + counts(s).asked, 0);
  const wrong = subjects.reduce((n, s) => n + counts(s).wrong, 0);

  const topics = course?.topics ?? [];
  const inserted = topics.filter((t) => t.origin === "inserted");
  // 보강 단원 제목 = 과목명. 어느 과목이 어느 단원이 됐는지 이걸로 잇는다.
  const insertedTitles = new Set(inserted.map((t) => t.title));
  const style = setup.style ? STYLE_LABEL[setup.style] : undefined;

  return (
    // ⚠️ `max-w-3xl`(768px)은 목차 사이드바(268px)와 함께 서면 1024px 창에서
    //    **좌우 여백이 0이 된다** — 카드 테두리가 사이드바 경계선에 딱 붙어
    //    겹쳐 보인다. 폭을 한 단계 줄이고 가로 여백을 크게 잡는다.
    <div className="mx-auto max-w-2xl px-10 pb-16 pt-8">
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

      {/* ── 한 박스. 위에서 아래로 읽으면 인과가 이어진다 ───────────── */}
      <div className="mt-6 overflow-hidden rounded-2xl border border-border-primary bg-white">
        {/* 머리 — 전체 결과 한 줄 */}
        <div className="border-b border-border-primary bg-bg-secondary px-6 py-5">
          <p className="text-[1.02rem] leading-relaxed text-text-primary">
            먼저 알아야 할 <strong>{total}가지</strong>를 확인해서{" "}
            <strong>{unknown}가지</strong>를 모른다고 하셨어요.
            {asked > 0 && (
              <>
                {" "}
                그중 <strong>{asked}개</strong>는 문항으로 확인했고{" "}
                <strong>{wrong}개</strong>를 틀리셨습니다.
              </>
            )}
          </p>
          <p className="mt-2 text-[0.88rem] font-semibold text-accent">
            → 그래서 목차 앞에 {inserted.length}개 단원을 채웠습니다.
          </p>
        </div>

        {/* 과목마다 한 줄기. 마지막 줄이 결과가 되도록 */}
        {subjects.map((s) => {
          const c = counts(s);
          const failed = s.items.filter((i) => i.verified === false);
          const declared = s.items.filter(
            (i) => i.known === "unknown" && i.verified !== false,
          );
          const knew = s.items.filter((i) => i.known === "known");
          const added = insertedTitles.has(s.subject);

          return (
            <div
              key={s.subject}
              className="border-b border-border-primary px-6 py-5 last:border-b-0"
            >
              <div className="mb-2.5 flex items-baseline justify-between gap-3">
                <h3 className="font-bold text-text-primary">{s.subject}</h3>
                <span className="shrink-0 text-[0.75rem] text-text-tertiary">
                  안다 {c.known} · 모른다 {c.unknown}
                  {c.asked > 0 && <> · 확인 문항 {c.asked}</>}
                </span>
              </div>

              <div className="space-y-1.5 text-[0.82rem] leading-relaxed">
                {failed.length > 0 && (
                  <p className="text-text-secondary">
                    <span className="font-semibold text-red-700">🔴 문항에서 틀림</span>{" "}
                    — {failed.map((i) => i.item).join(" · ")}
                  </p>
                )}
                {declared.length > 0 && (
                  <p className="text-text-secondary">
                    <span className="font-semibold">모른다고 답함</span> —{" "}
                    {declared.map((i) => i.item).join(" · ")}
                  </p>
                )}
                {knew.length > 0 && (
                  <p className="text-text-tertiary">
                    이미 아는 것 — {knew.map((i) => i.item).join(" · ")}
                  </p>
                )}
              </div>

              {/* 이 과목의 결론. **바로 위 문장들의 결과**로 읽히도록 붙여 둔다 */}
              {added ? (
                <p className="mt-3 rounded-lg bg-accent/5 px-3.5 py-2 text-[0.83rem] text-text-secondary">
                  <span className="font-bold text-accent">✚ 「{s.subject}」 단원</span>이
                  목차 맨 앞에 추가되었습니다.
                </p>
              ) : (
                <p className="mt-3 text-[0.8rem] text-text-tertiary">
                  충분히 알고 계셔서 단원을 따로 넣지 않았습니다.
                </p>
              )}
            </div>
          );
        })}

      </div>

      {/* 성향은 **카드를 따로 뗀다.** 목차는 여기서 확정되고 끝이지만 설명
          방식은 앞으로 계속 적용되는 것이라, 같은 상자에 두면 둘의 수명이
          뒤섞인다. 색은 위 상자와 같게 둔다 — 종류가 다른 게 아니라
          적용 기간이 다를 뿐이다. */}
      <div className="mt-5 rounded-2xl border border-border-primary bg-white">
        <div className="px-6 py-5">
          <p className="mb-2 text-[0.75rem] font-bold text-text-tertiary">
            설명은 이렇게 씁니다 — 앞으로 계속 적용됩니다
          </p>
          <p className="text-[0.9rem] text-text-primary">
            <strong>{setup.goal ? GOAL_LABEL[setup.goal] : "목표 미선택"}</strong>
            {setup.deadline_weeks != null && <> · {setup.deadline_weeks}주 남음</>}
            {style && (
              <>
                {" · "}
                <strong>{style.name}</strong>
              </>
            )}
          </p>
          {/* ⚠️ 문턱(2주)이 백엔드 `planner.URGENT_WEEKS`에도 있다. 거기를
              고치면 여기도 같이 고쳐야 한다. "시험인데 왜 안 줄이지"가
              화면에서 바로 풀리도록 이유까지 적는다. */}
          <p className="mt-1.5 text-[0.82rem] leading-relaxed text-text-secondary">
            {setup.goal === "exam"
              ? setup.deadline_weeks != null && setup.deadline_weeks <= 2
                ? "시간이 얼마 없어 핵심만 짧게 씁니다."
                : "기한이 넉넉해서 범위를 빠뜨리지 않도록 표준 분량으로 씁니다."
              : setup.goal === "work"
                ? "실무에 쓰시려는 자료라 왜 그런지까지 함께 씁니다."
                : setup.goal === "interest"
                  ? "부담 없이 훑는 자료라 핵심만 보여드립니다."
                  : "표준 분량으로 씁니다."}
            {style && <> {style.effect}.</>}
          </p>
          <p className="mt-3 text-[0.8rem] leading-relaxed text-text-tertiary">
            ⚡ 여기서부터{" "}
            <strong className="text-text-secondary">목차는 바뀌지 않습니다.</strong>{" "}
            학습하며 약한 곳이 드러나면 단원을 새로 끼우는 대신 그 목차의 설명을
            늘리거나 줄입니다.
          </p>
        </div>
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
