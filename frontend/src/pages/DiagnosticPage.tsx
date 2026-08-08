/**
 * 진단 — **시험이 아니라 설정이다.** 한 번 앉아서 1분 30초.
 *
 *   ① 분야 맞나       12.5 판정을 사람이 확인. **자동 검증이 없는 값이라
 *                     이 화면이 유일한 창구다**
 *   ② 카드 4장        같은 개념을 네 형식으로 써서 보여주고 고르게 한다
 *   ③ 과목 체크       안다/들어봤다/모른다 → "들어봤다"만 펼쳐서 항목별로
 *   ④ 확인 문항       자기신고가 뒤집힐 수 있는 곳에만. 과목당 1~2문항
 *   ⑤ 보강 마련       POST /supply → 목차 앞에 보강 단원이 끼워진다
 *
 * ⚠️ ②에 **학습 효과 근거는 없다**(meshing hypothesis, Pashler 2008).
 *    이건 성취가 아니라 이탈을 막는 장치다 — 읽기 싫은 형식이면 안 읽는다.
 *    그래서 문구가 "당신에게 맞는 학습법"이 아니라 "읽기 편한 쪽"이다.
 *
 * ④는 한 번에 다 안 온다. 답을 받아야 다음이 정해져서 빈 배열이 올 때까지
 * GET → POST를 반복한다(§features/course/api.ts).
 */
import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { clsx } from "clsx";
import {
  ArrowLeftIcon,
  CheckCircleIcon,
  WarningCircleIcon,
} from "@phosphor-icons/react";

import {
  answerPrereqs,
  answerSubjects,
  fetchCards,
  fetchProbes,
  fetchSetup,
  gradeProbes,
  saveConfig,
  supply,
  type DiagnosticSetup,
  type Known,
  type Probe,
  type Style,
} from "@/features/course/api";
import { toGoal, useCourseDrafts } from "@/features/course/store";
import { curriculumKeys } from "@/features/curriculum/queries/useCurriculum";

const STYLE_LABEL: Record<Style, string> = {
  metaphor: "비유로",
  definition: "정의로",
  table: "표로",
  why: "왜 쓰는지로",
};

const KNOWN_CHOICES: { value: Known; label: string; desc: string }[] = [
  { value: "known", label: "안다", desc: "설명할 수 있어요" },
  { value: "heard", label: "들어봤다", desc: "이름은 아는데 흐릿해요" },
  { value: "unknown", label: "모른다", desc: "처음 봐요" },
];

const WEEKS = [2, 4, 8, 12, 24];

type Phase = "field" | "cards" | "subjects" | "items" | "probes" | "supply" | "done";

const PHASE_STEP: Record<Phase, number> = {
  field: 1,
  cards: 2,
  subjects: 3,
  items: 3,
  probes: 4,
  supply: 4,
  done: 4,
};

function describe(error: unknown): string {
  const detail = (error as { response?: { data?: { detail?: string } } })?.response
    ?.data?.detail;
  return detail ?? (error as Error)?.message ?? String(error);
}

const cardBase = "border-2 rounded-xl bg-white text-left transition-all";
const cardState = (on: boolean) =>
  on
    ? "border-primary bg-black/[0.03]"
    : "border-border-primary hover:border-text-tertiary hover:bg-bg-secondary";

function Spinner({ label }: { label: string }) {
  return (
    <div className="flex flex-col items-center gap-3 py-16">
      <span className="h-8 w-8 animate-spin rounded-full border-[3px] border-border-primary border-t-accent" />
      <p className="text-[0.9rem] text-text-secondary">{label}</p>
    </div>
  );
}

export function DiagnosticPage() {
  const { courseId = "" } = useParams();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const drafts = useCourseDrafts((s) => s.drafts);
  const patchDraft = useCourseDrafts((s) => s.patch);
  const draft = drafts.find((d) => d.courseId === courseId);

  const [phase, setPhase] = useState<Phase>("field");
  const [setup, setSetup] = useState<DiagnosticSetup | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // ① 기간
  const [weeks, setWeeks] = useState<number | null>(null);
  // ② 카드
  const [cards, setCards] = useState<Partial<Record<Style, string>> | null>(null);
  const [concept, setConcept] = useState<string | null>(null);
  // ③ 과목 → 항목
  const [subjectAnswers, setSubjectAnswers] = useState<Record<string, Known>>({});
  const [expand, setExpand] = useState<string[]>([]);
  const [itemAnswers, setItemAnswers] = useState<Record<string, Known>>({});
  // ④ 문항
  const [probes, setProbes] = useState<Probe[]>([]);
  const [picks, setPicks] = useState<Record<string, number>>({});
  const [asked, setAsked] = useState(0);
  const [result, setResult] = useState<{ subjects: number; inserted: number } | null>(
    null,
  );

  useEffect(() => {
    let alive = true;
    fetchSetup(courseId)
      .then((s) => {
        if (!alive) return;
        setSetup(s);
        setWeeks(s.deadline_weeks ?? null);
      })
      .catch((e) => alive && setError(describe(e)));
    return () => {
      alive = false;
    };
  }, [courseId]);

  const subjects = setup?.subjects ?? [];
  const expandItems = useMemo(
    () => subjects.filter((s) => expand.includes(s.subject)),
    [subjects, expand],
  );

  // ── ① 분야 확인 → 목표·기간 저장 → 카드 ──────────────────────
  async function goCards() {
    if (!setup) return;
    setBusy(true);
    setError(null);
    try {
      await saveConfig(courseId, {
        goal: draft ? toGoal(draft.purpose) : undefined,
        deadline_weeks: weeks ?? undefined,
      });
      setPhase("cards");
      const got = await fetchCards(courseId);
      setCards(got.cards);
      setConcept(got.concept);
      // 카드 생성이 실패하면 빈 객체가 온다. 고를 게 없으면 건너뛴다 —
      // 형식 선택은 이탈 방지 장치지 진단의 필수 단계가 아니다.
      if (!Object.values(got.cards).some(Boolean)) setPhase("subjects");
    } catch (e) {
      setError(describe(e));
    } finally {
      setBusy(false);
    }
  }

  async function pickStyle(style: Style) {
    setBusy(true);
    try {
      await saveConfig(courseId, { style });
      setPhase("subjects");
    } catch (e) {
      setError(describe(e));
    } finally {
      setBusy(false);
    }
  }

  // ── ③ 과목 → 펼침 → 항목 ────────────────────────────────────
  async function submitSubjects() {
    setBusy(true);
    setError(null);
    try {
      const out = await answerSubjects(courseId, subjectAnswers);
      setSetup(out.setup);
      setExpand(out.expand);
      if (out.expand.length === 0) await startProbes();
      else setPhase("items");
    } catch (e) {
      setError(describe(e));
    } finally {
      setBusy(false);
    }
  }

  async function submitItems() {
    setBusy(true);
    setError(null);
    try {
      setSetup(await answerPrereqs(courseId, itemAnswers));
      await startProbes();
    } catch (e) {
      setError(describe(e));
    } finally {
      setBusy(false);
    }
  }

  // ── ④ 확인 문항 — 빈 배열이 올 때까지 GET → POST ────────────
  async function startProbes() {
    setPhase("probes");
    setProbes([]);
    setPicks({});
    const round = await fetchProbes(courseId);
    if (round.length === 0) await runSupply();
    else setProbes(round);
  }

  async function submitProbes() {
    setBusy(true);
    setError(null);
    try {
      const results: Record<string, boolean> = {};
      for (const p of probes) results[p.prereq_id] = picks[p.prereq_id] === p.answer_index;
      await gradeProbes(courseId, results);
      setAsked((n) => n + probes.length);
      setProbes([]);
      setPicks({});
      const next = await fetchProbes(courseId);
      if (next.length === 0) await runSupply();
      else setProbes(next);
    } catch (e) {
      setError(describe(e));
    } finally {
      setBusy(false);
    }
  }

  // ── ⑤ 보강 ──────────────────────────────────────────────────
  const supplied = useRef(false);
  async function runSupply() {
    if (supplied.current) return;
    supplied.current = true;
    setPhase("supply");
    try {
      const out = await supply(courseId);
      setResult({ subjects: out.subjects, inserted: out.inserted + out.updated });
      if (draft) patchDraft(draft.id, { diagnosed: true });
      // 보강 단원이 목차에 끼워졌다. 책장이 들고 있는 목차는 이제 낡았다.
      await qc.invalidateQueries({ queryKey: curriculumKeys.documents });
      await qc.invalidateQueries({ queryKey: curriculumKeys.document(courseId) });
      setPhase("done");
    } catch (e) {
      setError(describe(e));
      setPhase("done");
    }
  }

  // ── 그리기 ──────────────────────────────────────────────────
  const allSubjectsAnswered =
    subjects.length > 0 && subjects.every((s) => subjectAnswers[s.subject]);
  const allItemsAnswered = expandItems.every((s) =>
    s.items.every((i) => itemAnswers[i.id]),
  );
  const allPicked = probes.every((p) => picks[p.prereq_id] !== undefined);

  return (
    <div className="flex min-h-screen justify-center bg-bg-secondary px-4 py-10">
      <div className="w-full max-w-[640px]">
        <div className="rounded-2xl border border-border-primary bg-white p-12 shadow-lg max-[480px]:p-6">
          <div className="mb-4 flex items-center justify-between">
            <span className="text-sm font-semibold text-accent">
              STEP {PHASE_STEP[phase]} / 4
            </span>
            {setup && <span className="text-[0.8rem] text-text-tertiary">{setup.field}</span>}
          </div>

          {error && (
            <div className="mb-6 flex items-start gap-2 rounded-xl border border-red-200 bg-red-50/50 px-4 py-3 text-[0.85rem] text-red-700">
              <WarningCircleIcon weight="fill" className="mt-0.5 shrink-0 text-lg" />
              <span>{error}</span>
            </div>
          )}

          {!setup && !error && <Spinner label="자료를 읽는 중…" />}

          {/* ① 분야 맞나 */}
          {setup && phase === "field" && (
            <>
              <h2 className="mb-2 text-[1.75rem] font-bold tracking-tight text-primary">
                이 분야가 맞나요?
              </h2>
              <p className="mb-8 text-[0.95rem] text-text-secondary">
                올린 자료를 읽고 판단한 분야예요. 이 값으로 먼저 알아야 할 것을 찾아요.
              </p>

              <div className="mb-8 rounded-xl border-2 border-primary bg-black/[0.03] px-5 py-4">
                <div className="text-[1.05rem] font-bold text-text-primary">
                  {setup.field ?? "분야를 판단하지 못했어요"}
                </div>
                <div className="mt-1 text-[0.8rem] text-text-secondary">
                  {setup.documents.join(" · ")}
                </div>
              </div>

              <h3 className="mb-3 text-[0.95rem] font-semibold text-text-primary">
                언제까지 하실 건가요?
              </h3>
              <div className="mb-2 flex flex-wrap gap-2">
                {WEEKS.map((w) => (
                  <button
                    key={w}
                    onClick={() => setWeeks(w)}
                    className={clsx(
                      cardBase,
                      cardState(weeks === w),
                      "px-4 py-2 text-[0.9rem] font-medium text-text-primary",
                    )}
                  >
                    {w}주
                  </button>
                ))}
                <button
                  onClick={() => setWeeks(null)}
                  className={clsx(
                    cardBase,
                    cardState(weeks === null),
                    "px-4 py-2 text-[0.9rem] font-medium text-text-primary",
                  )}
                >
                  정하지 않음
                </button>
              </div>
              {setup.subjects.length > 0 && (
                <p className="mt-6 text-[0.85rem] text-text-tertiary">
                  자료 밖에서 먼저 알아야 할 것이 {setup.subjects.length}과목 ·{" "}
                  {setup.subjects.reduce((n, s) => n + s.items.length, 0)}개 있어요.
                </p>
              )}
            </>
          )}

          {/* ② 카드 4장 */}
          {phase === "cards" && (
            <>
              <h2 className="mb-2 text-[1.75rem] font-bold tracking-tight text-primary">
                어떤 설명이 읽기 편하세요?
              </h2>
              <p className="mb-8 text-[0.95rem] text-text-secondary">
                {concept ? `「${concept}」을 네 가지로 써봤어요. ` : ""}
                고른 쪽으로 설명을 씁니다.
              </p>
              {!cards ? (
                <Spinner label="네 가지로 써보는 중…" />
              ) : (
                <div className="flex flex-col gap-3">
                  {(Object.keys(STYLE_LABEL) as Style[])
                    .filter((k) => cards[k])
                    .map((k) => (
                      <button
                        key={k}
                        disabled={busy}
                        onClick={() => pickStyle(k)}
                        className={clsx(cardBase, cardState(false), "px-5 py-4")}
                      >
                        <div className="mb-1 text-[0.8rem] font-semibold text-accent">
                          {STYLE_LABEL[k]}
                        </div>
                        {/* `table`은 마크다운 표로 온다. 그대로 흘리면 `|`가
                            날것으로 보이므로 줄과 칸을 살려서 보여준다. */}
                        <div
                          className={clsx(
                            "whitespace-pre-wrap text-text-primary",
                            k === "table"
                              ? "font-mono text-[0.8rem] leading-relaxed"
                              : "text-[0.9rem] leading-relaxed",
                          )}
                        >
                          {cards[k]}
                        </div>
                      </button>
                    ))}
                </div>
              )}
            </>
          )}

          {/* ③-1 과목 */}
          {phase === "subjects" && (
            <>
              <h2 className="mb-2 text-[1.75rem] font-bold tracking-tight text-primary">
                이건 어느 정도 아세요?
              </h2>
              <p className="mb-8 text-[0.95rem] text-text-secondary">
                자료가 안 가르치는 것들이에요. 모르는 건 앞에 따로 넣어드릴게요.
              </p>
              <div className="flex flex-col gap-4">
                {subjects.map((s) => (
                  <div key={s.subject}>
                    <div className="mb-2 flex items-baseline gap-2">
                      <span className="font-semibold text-text-primary">{s.subject}</span>
                      <span className="text-[0.75rem] text-text-tertiary">
                        {s.items.length}개
                      </span>
                    </div>
                    <div className="grid grid-cols-3 gap-2">
                      {KNOWN_CHOICES.map((c) => (
                        <button
                          key={c.value}
                          onClick={() =>
                            setSubjectAnswers((a) => ({ ...a, [s.subject]: c.value }))
                          }
                          className={clsx(
                            cardBase,
                            cardState(subjectAnswers[s.subject] === c.value),
                            "px-3 py-2 text-center",
                          )}
                        >
                          <div className="text-[0.85rem] font-semibold text-text-primary">
                            {c.label}
                          </div>
                        </button>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}

          {/* ③-2 펼친 과목의 항목 */}
          {phase === "items" && (
            <>
              <h2 className="mb-2 text-[1.75rem] font-bold tracking-tight text-primary">
                조금 더 좁혀볼게요
              </h2>
              <p className="mb-8 text-[0.95rem] text-text-secondary">
                "들어봤다"고 하신 과목이에요. 아는 항목은 보강에서 빼드려요.
              </p>
              <div className="flex flex-col gap-6">
                {expandItems.map((s) => (
                  <div key={s.subject}>
                    <div className="mb-2 font-semibold text-text-primary">{s.subject}</div>
                    <div className="flex flex-col gap-2">
                      {s.items.map((item) => (
                        <div
                          key={item.id}
                          className="flex items-center gap-3 rounded-xl border border-border-primary px-4 py-2"
                        >
                          <span className="min-w-0 flex-1 truncate text-[0.9rem] text-text-primary">
                            {item.item}
                          </span>
                          <div className="flex shrink-0 gap-1">
                            {KNOWN_CHOICES.map((c) => (
                              <button
                                key={c.value}
                                onClick={() =>
                                  setItemAnswers((a) => ({ ...a, [item.id]: c.value }))
                                }
                                className={clsx(
                                  "rounded-lg border px-2 py-1 text-[0.75rem] transition-colors",
                                  itemAnswers[item.id] === c.value
                                    ? "border-primary bg-black/[0.03] font-semibold text-text-primary"
                                    : "border-border-primary text-text-secondary hover:bg-bg-secondary",
                                )}
                              >
                                {c.label}
                              </button>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}

          {/* ④ 확인 문항 */}
          {phase === "probes" && (
            <>
              <h2 className="mb-2 text-[1.75rem] font-bold tracking-tight text-primary">
                한 번만 확인할게요
              </h2>
              <p className="mb-8 text-[0.95rem] text-text-secondary">
                과목마다 한두 문항이에요. 틀려도 괜찮아요 — 그만큼 더 넣어드릴 뿐이에요.
                {asked > 0 && ` 지금까지 ${asked}문항.`}
              </p>
              {probes.length === 0 ? (
                <Spinner label="문항을 만드는 중…" />
              ) : (
                <div className="flex flex-col gap-6">
                  {probes.map((p) => (
                    <div key={p.prereq_id}>
                      <div className="mb-1 text-[0.75rem] font-semibold text-accent">
                        {p.subject}
                      </div>
                      <div className="mb-3 text-[0.95rem] font-semibold text-text-primary">
                        {p.stem}
                      </div>
                      <div className="flex flex-col gap-2">
                        {p.choices.map((choice, i) => (
                          <button
                            key={i}
                            onClick={() => setPicks((s) => ({ ...s, [p.prereq_id]: i }))}
                            className={clsx(
                              cardBase,
                              cardState(picks[p.prereq_id] === i),
                              "px-4 py-3 text-[0.875rem] leading-relaxed text-text-primary",
                            )}
                          >
                            {choice}
                          </button>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </>
          )}

          {phase === "supply" && <Spinner label="모자란 부분을 채우는 중…" />}

          {/* ⑤ 끝 */}
          {phase === "done" && (
            <div className="py-6 text-center">
              <CheckCircleIcon
                weight="fill"
                className="mx-auto mb-4 text-[3rem] text-emerald-500"
              />
              <h2 className="mb-2 text-[1.75rem] font-bold tracking-tight text-primary">
                준비됐어요
              </h2>
              <p className="mb-8 text-[0.95rem] text-text-secondary">
                {result
                  ? `${result.subjects}과목을 살펴서 ${result.inserted}개 단원을 목차 앞에 넣었어요.`
                  : "목차를 그대로 씁니다."}
                {asked > 0 && ` 문항 ${asked}개로 확인했어요.`}
              </p>
              <button
                onClick={() => navigate(`/curriculum/${encodeURIComponent(courseId)}`)}
                className="inline-flex items-center gap-2 rounded-xl bg-primary px-6 py-3 text-[0.9rem] font-semibold text-white shadow-sm transition-all hover:-translate-y-0.5 hover:bg-primary-hover"
              >
                학습 시작하기
              </button>
            </div>
          )}

          {/* 아래 버튼 */}
          {setup && phase !== "done" && phase !== "cards" && phase !== "supply" && (
            <div className="mt-10 flex items-center justify-between border-t border-border-primary pt-6">
              <button
                onClick={() => navigate("/library")}
                className="flex items-center gap-2 text-[13.3333px] font-medium text-text-secondary transition-colors hover:text-primary"
              >
                <ArrowLeftIcon /> 나중에 하기
              </button>
              <button
                disabled={
                  busy ||
                  (phase === "subjects" && !allSubjectsAnswered) ||
                  (phase === "items" && !allItemsAnswered) ||
                  (phase === "probes" && (probes.length === 0 || !allPicked))
                }
                onClick={() => {
                  if (phase === "field") void goCards();
                  else if (phase === "subjects") void submitSubjects();
                  else if (phase === "items") void submitItems();
                  else if (phase === "probes") void submitProbes();
                }}
                className={clsx(
                  "inline-flex items-center gap-2 rounded-xl bg-primary px-5 py-[0.6rem] text-[13.3333px] font-semibold text-white shadow-sm transition-all",
                  busy ||
                    (phase === "subjects" && !allSubjectsAnswered) ||
                    (phase === "items" && !allItemsAnswered) ||
                    (phase === "probes" && (probes.length === 0 || !allPicked))
                    ? "cursor-not-allowed opacity-50"
                    : "hover:-translate-y-0.5 hover:bg-primary-hover hover:shadow-md",
                )}
              >
                {busy ? "…" : phase === "field" ? "맞아요" : "다음"}
              </button>
            </div>
          )}
        </div>

        <p className="mt-4 text-center text-[0.75rem] text-text-tertiary">
          나중에 해도 돼요. 그때는 모르는 것으로 보고 전부 넣어드립니다.
        </p>
      </div>
    </div>
  );
}
