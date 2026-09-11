// 메타인지 분석 — **네 출처가 하나로 모인다**를 보여주는 유일한 화면.
//
// 이 화면이 없으면 진단·인출·복습·형성이 각각 어디선가 쌓이기만 하고, 그게
// 하나의 값이 된다는 주장을 확인할 자리가 없다. 그래서 여기서 제일 크게
// 보여주는 건 준비도 하나가 아니라 **그게 무엇으로 이루어졌는가**다.
//
// ⚠️ 비어 있는 출처를 숨기지 않는다. 진단이 0이면 누적이 사실상 3출처로 돌고
//    있다는 뜻이고, 그건 감출 게 아니라 보여줘야 하는 사실이다.
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ChartLineUpIcon, WarningCircleIcon } from "@phosphor-icons/react";

import { KIND_LABEL, type AttemptKind } from "@/features/curriculum/api/curriculum";
import { fetchAnalysis, type AnalysisDoc } from "@/features/curriculum/api/analysis";
import { Bar, pct } from "@/features/curriculum/components/bits";

// ⚠️ `diagnostic`이 빠져 있다. 진단(24)은 **문항 점수를 쌓지 않는다** —
//    "안다/모른다"를 받아 목차를 바꾼다(보강 단원 삽입). 그래서 이 막대에 넣으면
//    영원히 0이고, 화면이 "진단 기록이 없어요"라고 거짓말을 하게 된다.
//    진단이 한 일은 아래 `DiagnosisCard`가 따로 보여준다.
const KINDS: AttemptKind[] = ["retrieval", "review", "formative"];

// 가중치는 백엔드 mastery.WEIGHT와 같아야 한다. 화면에 왜 출처마다 무게가
// 다른지 설명하려면 값이 보여야 해서 여기 적는다.
const KIND_WEIGHT: Record<AttemptKind, string> = {
  diagnostic: "×0.5",
  retrieval: "×1.0",
  review: "×1.5",
  formative: "×2.0",
};

/** 진단이 한 일 — 점수가 아니라 **목차**를 바꿨다. */
function DiagnosisCard({ inserted }: { inserted: number }) {
  if (inserted === 0) return null;
  return (
    <div className="mb-8 rounded-2xl border border-accent/30 bg-accent/5 px-7 py-6">
      <h3 className="font-bold text-text-primary">진단이 한 일</h3>
      <p className="mt-0.5 mb-4 text-[0.85rem] text-text-secondary">
        진단은 점수를 쌓지 않습니다. <strong>배울 순서를 바꿉니다.</strong>
      </p>
      <div className="flex items-baseline gap-3">
        <span className="text-[1.75rem] font-bold tabular-nums text-accent">
          ✚ {inserted}
        </span>
        <span className="text-[0.9rem] text-text-secondary">
          모른다고 하신 과목을 <strong>교재 목차 앞에</strong> 단원으로 넣었습니다
        </span>
      </div>
    </div>
  );
}

const KIND_WHY: Record<AttemptKind, string> = {
  diagnostic: "배우기 전 답이라 증거가 약해요",
  retrieval: "방금 읽고 꺼낸 것",
  review: "시간이 지나고도 꺼낸 것 — 더 센 증거",
  formative: "개념을 가로질러 맞힌 것 — 가장 센 증거",
};

function Stat({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint?: string;
}) {
  return (
    <div className="rounded-2xl border border-border-primary bg-white px-6 py-5">
      <div className="text-[0.8rem] font-semibold text-text-tertiary">{label}</div>
      <div className="mt-1 text-[1.75rem] font-bold tabular-nums text-text-primary">
        {value}
      </div>
      {hint && <div className="mt-0.5 text-[0.8rem] text-text-tertiary">{hint}</div>}
    </div>
  );
}

function DocRow({ d }: { d: AnalysisDoc }) {
  return (
    <Link
      to={`/curriculum/${encodeURIComponent(d.docId)}`}
      className="block rounded-2xl border border-border-primary bg-white px-6 py-5 transition-colors hover:border-accent/50"
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <span className="font-bold text-text-primary">{d.title}</span>
        <span className="text-[0.85rem] text-text-secondary">
          화면 {d.sectionsDone}/{d.sectionsTotal}
          {d.sectionsDue > 0 && (
            <span className="ml-2 text-accent">🔁 복습 {d.sectionsDue}</span>
          )}
        </span>
      </div>
      <div className="mt-3 flex items-center gap-3">
        <div className="min-w-0 flex-1">
          <Bar value={d.readiness} />
        </div>
        <span className="w-12 shrink-0 text-right text-[0.85rem] font-semibold tabular-nums text-text-primary">
          {pct(d.readiness)}
        </span>
      </div>
      {d.weakestChapter && (
        <div className="mt-2.5 text-[0.83rem] text-text-tertiary">
          가장 약한 목차 — <strong className="text-text-secondary">{d.weakestChapter}</strong>
          {d.weakConcepts.length > 0 && <> · {d.weakConcepts.join(" · ")}</>}
        </div>
      )}
    </Link>
  );
}

export function AnalysisPage() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["curriculum", "analysis"],
    queryFn: fetchAnalysis,
  });

  const missing = data ? KINDS.filter((k) => !data.byKind[k]) : [];
  const maxKind = data ? Math.max(1, ...KINDS.map((k) => data.byKind[k] ?? 0)) : 1;

  return (
    <div className="mx-auto w-full max-w-[1100px] px-12 py-12">
      <div className="mb-9">
        <h2 className="mb-1 text-[2rem] font-extrabold tracking-tight text-text-primary">
          메타인지 분석
        </h2>
        <p className="text-text-secondary">
          진단은 <strong>배울 순서</strong>를 정하고, 그 뒤에 푼 문항들이{" "}
          <strong>하나의 준비도</strong>로 모입니다.
        </p>
      </div>

      {isLoading && <p className="text-text-secondary">불러오는 중…</p>}
      {isError && <p className="text-text-secondary">분석을 불러오지 못했습니다.</p>}

      {data && data.attemptsTotal === 0 && (
        <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-border-primary bg-white py-24 text-center">
          <ChartLineUpIcon className="mb-4 text-[3rem] text-text-tertiary" />
          <p className="font-semibold text-text-secondary">아직 푼 문항이 없어요</p>
          <p className="mt-1 text-[0.9rem] text-text-tertiary">
            자료를 하나 열고 화면을 학습하면 여기에 쌓입니다.
          </p>
        </div>
      )}

      {data && data.attemptsTotal > 0 && (
        <>
          <div className="mb-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Stat
              label="준비도"
              value={pct(data.readiness)}
              hint="이해도 × 진도 × 회상"
            />
            <Stat
              label="이해도"
              value={pct(data.understanding)}
              hint="망각을 뺀 값"
            />
            <Stat
              label="진도"
              value={`${data.sectionsDone} / ${data.sectionsTotal}`}
              hint="학습한 화면"
            />
            <Stat
              label="복습 대상"
              value={String(data.sectionsDue)}
              hint="지금 다시 꺼내야 하는 화면"
            />
          </div>

          <DiagnosisCard inserted={data.insertedChapters} />

          {/* ── 출처별 누적 ─────────────────────────────────── */}
          <section className="mb-8 rounded-2xl border border-border-primary bg-white px-7 py-6">
            <h3 className="font-bold text-text-primary">누적이 어디서 왔나</h3>
            <p className="mt-0.5 mb-5 text-[0.85rem] text-text-secondary">
              한 문항이 담는 정보량이 달라서 출처마다 무게가 다릅니다. 시도{" "}
              {data.attemptsTotal}건.
            </p>
            <div className="flex flex-col gap-3">
              {KINDS.map((k) => {
                const n = data.byKind[k] ?? 0;
                return (
                  <div key={k} className="flex items-center gap-4">
                    <div className="w-24 shrink-0">
                      <span className="font-semibold text-text-primary">
                        {KIND_LABEL[k]}
                      </span>
                      <span className="ml-1.5 text-[0.75rem] tabular-nums text-text-tertiary">
                        {KIND_WEIGHT[k]}
                      </span>
                    </div>
                    <div className="h-2.5 min-w-0 flex-1 overflow-hidden rounded-full bg-bg-secondary">
                      <div
                        className={n > 0 ? "h-full rounded-full bg-accent" : "h-full"}
                        style={{ width: `${(n / maxKind) * 100}%` }}
                      />
                    </div>
                    <span className="w-10 shrink-0 text-right text-[0.85rem] font-semibold tabular-nums text-text-primary">
                      {n}
                    </span>
                    <span className="hidden w-56 shrink-0 text-[0.78rem] text-text-tertiary lg:block">
                      {KIND_WHY[k]}
                    </span>
                  </div>
                );
              })}
            </div>

            {missing.length > 0 && (
              <div className="mt-5 flex items-start gap-2.5 rounded-xl bg-bg-secondary px-5 py-3.5">
                <WarningCircleIcon className="mt-0.5 shrink-0 text-[1.1rem] text-text-tertiary" />
                <p className="text-[0.85rem] text-text-secondary">
                  <strong>{missing.map((k) => KIND_LABEL[k]).join(" · ")}</strong>{" "}
                  기록이 아직 없어요. 그만큼 준비도의 근거가 얇습니다 — 빈 자리를
                  감추지 않고 그대로 보여드립니다.
                </p>
              </div>
            )}
          </section>

          {/* ── 약점 개념 ───────────────────────────────────── */}
          {data.weakConcepts.length > 0 && (
            <section className="mb-8 rounded-2xl border border-border-primary bg-white px-7 py-6">
              <h3 className="font-bold text-text-primary">자주 걸리는 개념</h3>
              <p className="mt-0.5 mb-4 text-[0.85rem] text-text-secondary">
                여러 목차에서 약점으로 잡힌 것부터. 다음 설명에 이걸 엮습니다.
              </p>
              <div className="flex flex-wrap gap-2">
                {data.weakConcepts.map(([name, n]) => (
                  <span
                    key={name}
                    className="rounded-lg bg-bg-secondary px-3.5 py-1.5 text-[0.85rem] text-text-primary"
                  >
                    {name}
                    {n > 1 && (
                      <span className="ml-1.5 text-[0.75rem] tabular-nums text-text-tertiary">
                        {n}곳
                      </span>
                    )}
                  </span>
                ))}
              </div>
            </section>
          )}

          {/* ── 자료별 ──────────────────────────────────────── */}
          <section>
            <h3 className="mb-3 font-bold text-text-primary">자료별</h3>
            <div className="flex flex-col gap-3">
              {data.documents.map((d) => (
                <DocRow key={d.docId} d={d} />
              ))}
            </div>
          </section>
        </>
      )}
    </div>
  );
}
