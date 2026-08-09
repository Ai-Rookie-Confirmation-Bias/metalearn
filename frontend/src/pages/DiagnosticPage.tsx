// 진단 화면 — **시험이 아니라 설정이다.**
//
// 문구를 그렇게 잡은 이유가 있다. 진단 문항 자동 생성은 실측에서 못 쓸 수준이었고
// (책 밖 1/6 · 책 안 1/4), 대신 "안다고 한 것만 표본으로 확인"하는 방식이 14/15로
// 됐다. 그래서 대부분은 체크리스트이고 ⑤만 문항이다.
//
// 화면 다섯 (docs/INTEGRATION.md §4 프론트):
//   ① 왜 배우나   ② 분야 맞나   ③ 어떤 설명이 편한가
//   ④ 선수 체크(과목 → 펼침)   ⑤ 확인 문항(없을 수 있다)
import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { clsx } from "clsx";
import {
  ArrowLeftIcon,
  ArrowRightIcon,
  CheckCircleIcon,
  SpinnerGapIcon,
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
  type DiagnosticCards,
  type DiagnosticSetup,
  type Goal,
  type Known,
  type Probe,
  type Style,
} from "@/features/diagnostic/api";

const GOALS: { value: Goal; label: string; hint: string }[] = [
  { value: "exam", label: "시험 준비", hint: "범위를 빠짐없이. 기한이 있으면 분량을 줄입니다" },
  { value: "work", label: "실무에 쓰려고", hint: "왜 그런지까지 깊게 봅니다" },
  { value: "interest", label: "관심이 있어서", hint: "부담 없이 훑습니다" },
];

const WEEKS = [1, 2, 4, 8];

// ⚠️ 문구 주의 — "당신에게 맞는 학습법"이 아니다. 러닝 스타일 맞춤에 학습 효과
//    근거는 없다(Pashler 2008). 이건 성취가 아니라 **이탈을 막는 장치**다.
const STYLE_LABEL: Record<Style, string> = {
  metaphor: "비유로",
  definition: "정의부터",
  table: "표로 비교",
  why: "왜 그런지부터",
};

const KNOWN_CHOICES: { value: Known; label: string }[] = [
  { value: "known", label: "안다" },
  { value: "heard", label: "들어봤다" },
  { value: "unknown", label: "모른다" },
];

const STEPS = ["왜 배우나", "분야", "설명 방식", "아는 것", "확인", "채우기"];

function Choice({
  active,
  onClick,
  children,
  className,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={clsx(
        "rounded-xl border-2 px-5 py-3 text-left transition-colors",
        active
          ? "border-accent bg-accent/5 text-text-primary"
          : "border-border-primary text-text-secondary hover:border-accent/50",
        className,
      )}
    >
      {children}
    </button>
  );
}

function KnownRow({
  label,
  why,
  value,
  onPick,
}: {
  label: string;
  why?: string | null;
  value: Known | undefined;
  onPick: (k: Known) => void;
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border-primary px-5 py-3.5">
      <div className="min-w-0">
        <div className="font-semibold text-text-primary">{label}</div>
        {why && <div className="mt-0.5 text-[0.85rem] text-text-tertiary">{why}</div>}
      </div>
      <div className="flex shrink-0 gap-1.5">
        {KNOWN_CHOICES.map((c) => (
          <button
            key={c.value}
            type="button"
            onClick={() => onPick(c.value)}
            className={clsx(
              "rounded-lg px-3.5 py-1.5 text-[0.85rem] font-semibold transition-colors",
              value === c.value
                ? "bg-accent text-white"
                : "bg-bg-secondary text-text-secondary hover:bg-accent/10",
            )}
          >
            {c.label}
          </button>
        ))}
      </div>
    </div>
  );
}

export function DiagnosticPage() {
  const { docId = "" } = useParams();
  const navigate = useNavigate();

  const [step, setStep] = useState(0);
  const [setup, setSetup] = useState<DiagnosticSetup | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [goal, setGoal] = useState<Goal | null>(null);
  const [weeks, setWeeks] = useState<number | null>(null);
  const [style, setStyle] = useState<Style | null>(null);

  const [cards, setCards] = useState<DiagnosticCards | null>(null);
  const [subjectAns, setSubjectAns] = useState<Record<string, Known>>({});
  const [expand, setExpand] = useState<string[] | null>(null);
  const [itemAns, setItemAns] = useState<Record<string, Known>>({});
  const [probes, setProbes] = useState<Probe[] | null>(null);
  const [picked, setPicked] = useState<Record<string, number>>({});
  // 진단이 끝나고 조달까지 마친 결과. null이면 아직 진행 중이다.
  const [done, setDone] = useState<{ subjects: number; inserted: number } | null>(
    null,
  );
  // 몇 문항을 실제로 물었나. 라운드가 여러 번이라 누적한다.
  const [asked, setAsked] = useState(0);

  useEffect(() => {
    let alive = true;
    setError(null);
    fetchSetup(docId)
      .then((s) => {
        if (!alive) return;
        setSetup(s);
        setGoal(s.goal);
        setWeeks(s.deadline_weeks);
        setStyle(s.style);
      })
      .catch(() =>
        alive &&
        setError(
          "진단은 수업(코스)에만 있습니다. 자료 하나를 열었다면 이 화면은 건너뜁니다.",
        ),
      );
    return () => {
      alive = false;
    };
  }, [docId]);

  // ③에 들어갈 때 카드를 부른다 — LLM 1콜이라 미리 부르지 않는다.
  useEffect(() => {
    if (step !== 2 || cards) return;
    let alive = true;
    setBusy(true);
    fetchCards(docId)
      .then((c) => alive && setCards(c))
      .catch(() => alive && setCards({ concept: null, cards: {} }))
      .finally(() => alive && setBusy(false));
    return () => {
      alive = false;
    };
  }, [step, cards, docId]);

  const subjects = setup?.subjects ?? [];
  // 펼칠 과목만 항목을 묻는다. 전부 물으면 실측 54개 — 과목으로 먼저 거르면 30개.
  const expanded = useMemo(
    () => (expand ? subjects.filter((s) => expand.includes(s.subject)) : []),
    [expand, subjects],
  );

  const back = () => (step === 0 ? navigate(`/curriculum/${docId}`) : setStep((s) => s - 1));

  async function next() {
    setBusy(true);
    setError(null);
    try {
      if (step === 0) {
        await saveConfig(docId, { goal: goal ?? undefined, deadline_weeks: weeks });
        setStep(1);
      } else if (step === 1) {
        setStep(2);
      } else if (step === 2) {
        if (style) await saveConfig(docId, { style });
        setStep(3);
      } else if (step === 3) {
        if (expand === null) {
          // ④-1 과목 단위 → 서버가 펼칠 과목을 정한다
          const r = await answerSubjects(docId, subjectAns);
          setSetup(r.setup);
          setExpand(r.expand);
          if (r.expand.length === 0) await toProbes();
        } else {
          // ④-2 펼친 과목의 항목별 답
          if (Object.keys(itemAns).length > 0) {
            setSetup(await answerPrereqs(docId, itemAns));
          }
          await toProbes();
        }
      } else if (step === 4) {
        const results: Record<string, boolean> = {};
        (probes ?? []).forEach((p, i) => {
          const got = picked[String(i)];
          if (got !== undefined) results[p.prereq_id] = got === p.answer_index;
        });
        await gradeProbes(docId, results);
        setAsked((n) => n + (probes?.length ?? 0));
        // **한 라운드로 안 끝난다.** 맞힌 과목은 한 번 더 묻는다 — 4지선다는
        // 찍어서 맞으니 한 번으로는 못 믿는다. 빈 배열이 올 때까지 돈다.
        await toProbes();
      }
    } catch {
      setError("저장하지 못했습니다. 잠시 후 다시 시도해 주세요.");
    } finally {
      setBusy(false);
    }
  }

  async function toProbes() {
    const p = await fetchProbes(docId);
    // ⑤는 **빈 목록일 수 있다** — 다 끝났거나, 정답을 못 세워 문항을 못 냈거나.
    // 어느 쪽이든 여기서 진단이 끝나고 조달로 넘어간다.
    if (p.length === 0) {
      setProbes([]);
      await runSupply();
      return;
    }
    setProbes(p);
    setPicked({});
    setStep(4);
  }

  /** 26·27 — 모르는 과목의 자료를 마련해 목차 앞에 끼운다.
   *
   *  실패해도 진단 결과는 이미 저장돼 있다. 보강만 없는 채로 끝낸다. */
  async function runSupply() {
    setStep(5);
    try {
      const out = await supply(docId);
      setDone({ subjects: out.subjects, inserted: out.inserted + out.updated });
    } catch {
      setDone({ subjects: 0, inserted: 0 });
    }
  }

  const canNext =
    step === 0
      ? goal !== null
      : step === 3 && expand === null
        ? subjects.length > 0 && subjects.every((s) => subjectAns[s.subject])
        : true;

  if (error && !setup) {
    return (
      <div className="mx-auto max-w-[680px] px-8 py-24 text-center">
        <p className="text-text-secondary">{error}</p>
        <button
          type="button"
          onClick={() => navigate(`/curriculum/${docId}`)}
          className="mt-6 rounded-xl bg-accent px-6 py-2.5 font-semibold text-white"
        >
          학습으로 가기
        </button>
      </div>
    );
  }

  if (done) {
    return (
      <div className="mx-auto max-w-[680px] px-8 py-24 text-center">
        <CheckCircleIcon className="mx-auto mb-5 text-[3.5rem] text-accent" weight="fill" />
        <h2 className="text-[1.75rem] font-bold text-text-primary">진단이 끝났어요</h2>
        <p className="mt-2 text-text-secondary">
          여기서 답한 것은 <strong>분량과 설명 방식</strong>을 정하는 데 쓰입니다.
          학습하면서 계속 다시 재요.
        </p>
        {done.inserted > 0 && (
          <p className="mt-4 rounded-xl bg-bg-secondary px-5 py-3 text-[0.9rem] text-text-secondary">
            먼저 알아야 할 <strong>{done.subjects}과목</strong>을 살펴서{" "}
            <strong>{done.inserted}개 단원</strong>을 목차 앞에 넣었어요
            {asked > 0 && ` (확인 문항 ${asked}개)`}.
          </p>
        )}
        <button
          type="button"
          onClick={() => navigate(`/curriculum/${docId}`)}
          className="mt-8 inline-flex items-center gap-2 rounded-xl bg-accent px-7 py-3 font-semibold text-white"
        >
          학습 시작하기 <ArrowRightIcon />
        </button>
      </div>
    );
  }

  return (
    <div className="mx-auto w-full max-w-[760px] px-8 py-12">
      <div className="mb-2 flex items-center gap-2 text-[0.85rem] font-semibold">
        {STEPS.map((s, i) => (
          <span key={s} className={i === step ? "text-accent" : "text-text-tertiary"}>
            {i > 0 && <span className="mr-2 text-border-primary">·</span>}
            {s}
          </span>
        ))}
      </div>
      <p className="mb-8 text-[0.9rem] text-text-tertiary">
        시험이 아니에요. <strong>어떻게 가르칠지 정하려고</strong> 묻는 거예요.
      </p>

      {step === 0 && (
        <>
          <h2 className="mb-2 text-[1.75rem] font-bold tracking-tight text-text-primary">
            이 자료를 왜 배우시나요?
          </h2>
          <p className="mb-7 text-[0.95rem] text-text-secondary">
            목적에 따라 설명 분량이 달라져요.
          </p>
          <div className="flex flex-col gap-3">
            {GOALS.map((g) => (
              <Choice key={g.value} active={goal === g.value} onClick={() => setGoal(g.value)}>
                <div className="font-semibold text-text-primary">{g.label}</div>
                <div className="mt-0.5 text-[0.85rem] text-text-tertiary">{g.hint}</div>
              </Choice>
            ))}
          </div>

          {goal === "exam" && (
            <div className="mt-7">
              <div className="mb-3 font-semibold text-text-primary">시험까지 얼마나 남았나요?</div>
              <div className="flex flex-wrap gap-2">
                {WEEKS.map((w) => (
                  <Choice key={w} active={weeks === w} onClick={() => setWeeks(w)}>
                    {w}주
                  </Choice>
                ))}
                <Choice active={weeks === null} onClick={() => setWeeks(null)}>
                  정해지지 않음
                </Choice>
              </div>
              <p className="mt-3 text-[0.85rem] text-text-tertiary">
                기간이 짧으면 아는 단원을 줄이고 모르는 쪽에 시간을 씁니다.
              </p>
            </div>
          )}
        </>
      )}

      {step === 1 && (
        <>
          <h2 className="mb-2 text-[1.75rem] font-bold tracking-tight text-text-primary">
            이 분야가 맞나요?
          </h2>
          <p className="mb-7 text-[0.95rem] text-text-secondary">
            자료를 읽고 판단한 값이에요. 틀리면 선수 개념을 엉뚱하게 잡습니다.
          </p>
          <div className="rounded-2xl border border-border-primary bg-bg-secondary px-7 py-8 text-center">
            <div className="text-[1.5rem] font-bold text-text-primary">
              {setup?.field ?? "판정하지 못했어요"}
            </div>
            {setup?.documents?.length ? (
              <div className="mt-2 text-[0.85rem] text-text-tertiary">
                {setup.documents.join(" · ")}
              </div>
            ) : null}
          </div>
          <p className="mt-4 text-[0.85rem] text-text-tertiary">
            지금은 확인만 받습니다. 고치는 기능은 아직 없어요 — 다르면 알려주세요.
          </p>
        </>
      )}

      {step === 2 && (
        <>
          <h2 className="mb-2 text-[1.75rem] font-bold tracking-tight text-text-primary">
            어떤 설명이 읽기 편한가요?
          </h2>
          <p className="mb-7 text-[0.95rem] text-text-secondary">
            같은 개념{cards?.concept ? ` (${cards.concept})` : ""}을 네 가지로 써봤어요.
            읽기 편한 쪽을 고르시면 그 방식으로 설명합니다.
          </p>
          {busy && !cards ? (
            <div className="flex items-center gap-2 py-16 text-text-tertiary">
              <SpinnerGapIcon className="animate-spin" /> 네 가지로 써보는 중…
            </div>
          ) : Object.keys(cards?.cards ?? {}).length === 0 ? (
            <p className="rounded-xl bg-bg-secondary px-5 py-6 text-text-secondary">
              예시를 만들지 못했어요. 이 단계는 건너뛰어도 됩니다.
            </p>
          ) : (
            <div className="grid gap-3 md:grid-cols-2">
              {(Object.keys(cards?.cards ?? {}) as Style[]).map((k) => (
                <Choice
                  key={k}
                  active={style === k}
                  onClick={() => setStyle(k)}
                  className="h-full"
                >
                  <div className="mb-1.5 text-[0.8rem] font-bold text-accent">
                    {STYLE_LABEL[k]}
                  </div>
                  {/* ⚠️ `whitespace-pre-wrap`이 없으면 표 카드가 죽는다 — 서버는
                      개행이 있는 마크다운 표를 주는데 기본 white-space가 그걸
                      한 줄로 뭉개서, "표로 비교"를 고르라면서 표를 안 보여주게 된다. */}
                  <div
                    className={clsx(
                      "whitespace-pre-wrap text-text-secondary",
                      k === "table"
                        ? "overflow-x-auto font-mono text-[0.72rem] leading-snug"
                        : "text-[0.9rem] leading-relaxed",
                    )}
                  >
                    {cards?.cards[k]}
                  </div>
                </Choice>
              ))}
            </div>
          )}
        </>
      )}

      {step === 3 && (
        <>
          <h2 className="mb-2 text-[1.75rem] font-bold tracking-tight text-text-primary">
            {expand === null ? "이미 아는 게 있나요?" : "조금 더 자세히"}
          </h2>
          <p className="mb-7 text-[0.95rem] text-text-secondary">
            {expand === null
              ? "아는 것은 설명을 줄이고, 모르는 것은 먼저 채웁니다."
              : "“들어봤다”고 하신 것만 항목별로 여쭤봐요."}
          </p>

          {expand === null ? (
            <div className="flex flex-col gap-2.5">
              {subjects.length === 0 && (
                <p className="rounded-xl bg-bg-secondary px-5 py-6 text-text-secondary">
                  확인할 선수 개념이 없어요. 다음으로 넘어가세요.
                </p>
              )}
              {subjects.map((s) => (
                <KnownRow
                  key={s.subject}
                  label={s.subject}
                  why={`${s.items.length}개 항목${s.ordered ? " · 순서가 있어요" : ""}`}
                  value={subjectAns[s.subject]}
                  onPick={(k) => setSubjectAns((p) => ({ ...p, [s.subject]: k }))}
                />
              ))}
            </div>
          ) : (
            <div className="flex flex-col gap-6">
              {expanded.length === 0 && (
                <p className="rounded-xl bg-bg-secondary px-5 py-6 text-text-secondary">
                  더 물어볼 게 없어요.
                </p>
              )}
              {expanded.map((s) => (
                <div key={s.subject}>
                  <div className="mb-2.5 font-bold text-text-primary">{s.subject}</div>
                  <div className="flex flex-col gap-2">
                    {s.items.map((it) => (
                      <KnownRow
                        key={it.id}
                        label={it.item}
                        why={it.why}
                        value={itemAns[it.id] ?? it.known ?? undefined}
                        onPick={(k) => setItemAns((p) => ({ ...p, [it.id]: k }))}
                      />
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {step === 4 && (
        <>
          <h2 className="mb-2 text-[1.75rem] font-bold tracking-tight text-text-primary">
            안다고 하신 것 중 몇 개만
          </h2>
          <p className="mb-7 text-[0.95rem] text-text-secondary">
            과목마다 한두 문항이에요. 틀려도 괜찮아요 — 그만큼 앞에 더 넣어드릴 뿐이에요.
          </p>
          <div className="flex flex-col gap-6">
            {(probes ?? []).map((p, i) => (
              <div key={p.prereq_id} className="rounded-2xl border border-border-primary p-6">
                <div className="mb-1 text-[0.8rem] font-semibold text-text-tertiary">
                  {p.subject} · {p.item}
                </div>
                <div className="mb-4 font-semibold text-text-primary">{p.stem}</div>
                <div className="flex flex-col gap-2">
                  {p.choices.map((c, ci) => (
                    <Choice
                      key={ci}
                      active={picked[String(i)] === ci}
                      onClick={() => setPicked((prev) => ({ ...prev, [String(i)]: ci }))}
                    >
                      {c}
                    </Choice>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      {step === 5 && (
        <div className="flex flex-col items-center gap-4 py-24 text-center">
          <SpinnerGapIcon className="animate-spin text-[2.5rem] text-accent" />
          <p className="font-semibold text-text-primary">모자란 부분을 채우는 중…</p>
          <p className="text-[0.9rem] text-text-tertiary">
            모른다고 하신 과목마다 무엇을 가르칠지 정리하고 있어요. 과목당 몇 초 걸려요.
          </p>
        </div>
      )}

      {error && setup && (
        <p className="mt-6 rounded-xl bg-red-50 px-5 py-3 text-[0.9rem] text-red-600">{error}</p>
      )}

      <div
        className={clsx(
          "mt-10 flex items-center justify-between border-t border-border-primary pt-6",
          step === 5 && "hidden",
        )}
      >
        <button
          type="button"
          onClick={back}
          className="inline-flex items-center gap-2 text-text-secondary hover:text-text-primary"
        >
          <ArrowLeftIcon /> {step === 0 ? "학습으로" : "이전"}
        </button>
        <button
          type="button"
          onClick={next}
          disabled={!canNext || busy}
          className={clsx(
            "inline-flex items-center gap-2 rounded-xl px-7 py-3 font-semibold text-white transition-opacity",
            canNext && !busy ? "bg-accent" : "cursor-not-allowed bg-text-tertiary/40",
          )}
        >
          {busy ? <SpinnerGapIcon className="animate-spin" /> : null}
          {step === 4 ? "채점하기" : "다음"}
        </button>
      </div>
    </div>
  );
}
