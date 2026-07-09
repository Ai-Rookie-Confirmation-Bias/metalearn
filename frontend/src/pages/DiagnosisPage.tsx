/**
 * 온보딩 진단 — /diagnosis/:courseId (진단 재설계).
 *   성향 문항(즉답) → 스타일 프로브 → 기반지식 체크 → 프로필 카드 → 책장.
 *
 * 서버가 진실: phase/disposition/probe/question/result는 OnboardingState로만 갱신.
 * 종료 시 서버가 finalize_onboarding(전 절 todo 시딩 + 프로필 확정)까지 처리한다.
 */
import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { clsx } from "clsx";
import {
  MagnifyingGlassIcon,
  SparkleIcon,
  UserCircleIcon,
  WarningCircleIcon,
} from "@phosphor-icons/react";

import { apiErrorMessage } from "@/shared/api/errors";
import {
  answerOnboarding,
  startOnboarding,
} from "@/features/diagnostic/api/onboardingApi";
import { getCourses } from "@/features/library/api/getCourses";
import type { OnboardingResult, OnboardingState, QuestionOut, QuestionType } from "@/features/diagnostic/types";

const QTYPE_LABEL: Record<QuestionType, string> = {
  mcq: "선택형",
  cloze: "빈칸 채우기",
  inverse: "떠올려 쓰기",
};

type Phase = "starting" | "active" | "done" | "start_error";

function Spinner({ className }: { className?: string }) {
  return (
    <span
      className={clsx(
        "inline-block h-5 w-5 animate-spin rounded-full border-2 border-text-tertiary/40 border-t-accent",
        className,
      )}
    />
  );
}

function CenterNotice({
  icon,
  title,
  desc,
  action,
}: {
  icon: React.ReactNode;
  title: string;
  desc: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center py-16 text-center">
      <div className="mb-5">{icon}</div>
      <h2 className="mb-2 text-[1.4rem] font-bold tracking-tight text-text-primary">{title}</h2>
      <p className="max-w-[440px] whitespace-pre-line text-[0.95rem] leading-relaxed text-text-secondary">
        {desc}
      </p>
      {action && <div className="mt-8">{action}</div>}
    </div>
  );
}

function ProfileCard({ result }: { result: OnboardingResult }) {
  return (
    <div className="rounded-2xl border border-accent/20 bg-accent/[0.04] p-8 text-left">
      <div className="mb-4 flex items-center gap-2 text-accent">
        <SparkleIcon className="text-xl" weight="fill" />
        <span className="text-sm font-semibold">나의 학습 성향</span>
      </div>
      <h3 className="mb-3 text-[1.35rem] font-bold text-text-primary">{result.label}</h3>
      <ul className="mb-6 space-y-2">
        {result.traits.map((t) => (
          <li key={t} className="text-[0.92rem] leading-relaxed text-text-secondary">
            · {t}
          </li>
        ))}
      </ul>
      {result.foundation_gaps.length > 0 && (
        <div className="rounded-xl border border-border-primary bg-white/80 p-4">
          <p className="mb-2 text-[0.85rem] font-semibold text-text-primary">
            기반지식에서 확인된 보강 포인트
          </p>
          <ul className="space-y-1 text-[0.85rem] text-text-secondary">
            {result.foundation_gaps.map((g) => (
              <li key={g.concept_id}>
                {g.concept_name}
                {g.missing.length > 0 && (
                  <span className="text-text-tertiary"> — {g.missing.join(", ")}</span>
                )}
              </li>
            ))}
          </ul>
          <p className="mt-2 text-[0.8rem] text-text-tertiary">
            학습 중 필요한 선행 내용은 자동으로 끼워 넣어요. 내용은 줄이지 않아요.
          </p>
        </div>
      )}
    </div>
  );
}

function QuizPanel({
  question,
  busy,
  errorMsg,
  onSubmit,
}: {
  question: QuestionOut;
  busy: boolean;
  errorMsg: string | null;
  onSubmit: (input: { selected_index?: number; answer_text?: string }) => void;
}) {
  const [picked, setPicked] = useState<number | null>(null);
  const [text, setText] = useState("");

  return (
    <>
      <p className="mb-2 text-[0.8rem] font-semibold text-text-tertiary">
        {question.concept_name} · {QTYPE_LABEL[question.qtype]}
      </p>
      <h2 className="mb-6 whitespace-pre-wrap text-[1.15rem] font-semibold leading-relaxed text-text-primary">
        {question.question}
      </h2>
      {question.qtype === "mcq" ? (
        <div className="flex flex-col gap-3">
          {question.options.map((opt, i) => (
            <button
              key={i}
              type="button"
              disabled={busy}
              onClick={() => {
                setPicked(i);
                void onSubmit({ selected_index: i });
              }}
              className={clsx(
                "flex items-center gap-4 rounded-xl border px-5 py-4 text-left text-[0.95rem] transition-all",
                picked === i
                  ? "border-accent bg-accent/[0.06] font-semibold text-text-primary"
                  : "border-border-primary bg-white text-text-primary hover:border-accent hover:bg-accent/[0.02]",
                busy && "cursor-default",
              )}
            >
              <span
                className={clsx(
                  "flex h-6 w-6 shrink-0 items-center justify-center rounded-full border text-[0.8rem] font-bold",
                  picked === i
                    ? "border-accent bg-accent text-white"
                    : "border-border-primary text-text-tertiary",
                )}
              >
                {String.fromCharCode(65 + i)}
              </span>
              <span>{opt}</span>
            </button>
          ))}
        </div>
      ) : (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (text.trim() && !busy) onSubmit({ answer_text: text.trim() });
          }}
          className="flex gap-2"
        >
          <input
            value={text}
            onChange={(e) => setText(e.target.value)}
            disabled={busy}
            placeholder="정답을 직접 떠올려 입력해주세요"
            autoFocus
            className="flex-1 rounded-xl border border-border-primary bg-white px-4 py-3 text-[0.95rem] text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none disabled:bg-bg-secondary"
          />
          <button
            type="submit"
            disabled={busy || !text.trim()}
            className="shrink-0 rounded-xl bg-primary px-6 py-3 text-[0.9rem] font-semibold text-white transition-colors hover:bg-primary-hover disabled:cursor-not-allowed disabled:opacity-50"
          >
            제출
          </button>
        </form>
      )}
      {busy && (
        <p className="mt-4 flex items-center gap-2 text-[0.9rem] text-text-tertiary">
          <Spinner /> 다음 단계를 준비하고 있어요…
        </p>
      )}
      {errorMsg && !busy && (
        <p className="mt-4 text-[0.9rem] text-red-600">제출 실패: {errorMsg}</p>
      )}
    </>
  );
}

export function DiagnosisPage() {
  const { courseId } = useParams<{ courseId: string }>();
  const navigate = useNavigate();

  const [phase, setPhase] = useState<Phase>("starting");
  const [state, setState] = useState<OnboardingState | null>(null);
  const [busy, setBusy] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const startedRef = useRef(false);

  // 방금 업로드한 코스는 파싱·시드가 백그라운드로 도는 중일 수 있다.
  // 커리큘럼(섹션)이 생기기 전 온보딩을 시작하면 대표 개념이 없어 실패하므로,
  // sectionsTotal>0 이 될 때까지 폴링한 뒤 온보딩을 시작한다.
  async function waitForCourseReady(id: string) {
    const deadline = Date.now() + 180_000; // 최대 3분
    for (;;) {
      try {
        const courses = await getCourses();
        const c = courses.find((x) => x.id === id);
        if (c && c.sectionsTotal > 0) return;
      } catch {
        // 일시 오류 — 계속 폴링
      }
      if (Date.now() > deadline) {
        throw new Error(
          "커리큘럼 생성이 아직 끝나지 않았어요. 잠시 후 다시 시도해주세요.",
        );
      }
      await new Promise((r) => setTimeout(r, 2500));
    }
  }

  async function start() {
    if (!courseId) return;
    setPhase("starting");
    setErrorMsg(null);
    try {
      await waitForCourseReady(courseId);
      const s = await startOnboarding(courseId);
      applyState(s);
    } catch (e) {
      setErrorMsg(apiErrorMessage(e));
      setPhase("start_error");
    }
  }

  function applyState(s: OnboardingState) {
    setState(s);
    if (s.done && s.result) {
      setPhase("done");
    } else {
      setPhase("active");
    }
  }

  useEffect(() => {
    if (startedRef.current) return;
    startedRef.current = true;
    void start();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function submitAnswer(input: {
    choice_index?: number;
    selected_index?: number;
    answer_text?: string;
  }) {
    if (!state || busy) return;
    setBusy(true);
    setErrorMsg(null);
    try {
      const payload =
        state.phase === "quiz" && state.question
          ? { ...input, question_id: state.question.id }
          : input;
      const next = await answerOnboarding(state.session_id, payload);
      applyState(next);
    } catch (e) {
      setErrorMsg(apiErrorMessage(e));
    } finally {
      setBusy(false);
    }
  }

  const pct =
    state && state.total_steps > 0
      ? Math.round(((state.step - 1) / state.total_steps) * 100)
      : 0;

  const phaseLabel =
    state?.phase === "disposition"
      ? "학습 성향"
      : state?.phase === "probe"
        ? "설명 스타일"
        : state?.phase === "quiz"
          ? "기반지식 체크"
          : "";

  return (
    <div className="flex min-h-screen items-center justify-center bg-bg-secondary px-4 py-10">
      <div className="w-full max-w-[720px] rounded-2xl border border-border-primary bg-white p-12 shadow-lg max-[480px]:p-6">
        {phase === "starting" && (
          <CenterNotice
            icon={<Spinner className="h-9 w-9 border-[3px]" />}
            title="학습을 준비하고 있어요"
            desc={
              "교재로 커리큘럼을 만들고,\n당신의 학습 성향을 볼 준비를 하고 있어요.\n최대 1~2분 정도 걸릴 수 있어요."
            }
          />
        )}

        {phase === "start_error" && (
          <CenterNotice
            icon={<WarningCircleIcon className="text-[3rem] text-red-500" />}
            title="온보딩을 시작하지 못했어요"
            desc={errorMsg ?? "알 수 없는 오류가 발생했어요."}
            action={
              <div className="flex gap-3">
                <button
                  onClick={() => void start()}
                  className="rounded-xl bg-primary px-6 py-3 text-[0.9rem] font-semibold text-white hover:bg-primary-hover"
                >
                  다시 시도
                </button>
                <button
                  onClick={() => navigate("/library")}
                  className="rounded-xl border border-border-primary px-6 py-3 text-[0.9rem] font-semibold text-text-secondary hover:bg-bg-secondary"
                >
                  책장으로
                </button>
              </div>
            }
          />
        )}

        {phase === "done" && state?.result && (
          <CenterNotice
            icon={<UserCircleIcon className="text-[3rem] text-accent" weight="duotone" />}
            title="준비 완료!"
            desc=""
            action={
              <div className="w-full max-w-[520px] space-y-6">
                <ProfileCard result={state.result} />
                <button
                  onClick={() => navigate("/library")}
                  className="w-full rounded-xl bg-primary px-6 py-3.5 text-[0.95rem] font-semibold text-white hover:bg-primary-hover"
                >
                  책장에서 학습 시작하기
                </button>
              </div>
            }
          />
        )}

        {phase === "active" && state && (
          <>
            <div className="mb-2 flex items-center justify-between">
              <span className="flex items-center gap-1.5 text-sm font-semibold text-accent">
                <MagnifyingGlassIcon /> 온보딩 · {phaseLabel}
              </span>
              <span className="text-[0.85rem] font-semibold text-text-secondary">
                {state.step} / {state.total_steps}
              </span>
            </div>
            <div className="mb-8 h-1.5 w-full overflow-hidden rounded-full bg-bg-secondary">
              <div
                className="h-full rounded-full bg-accent transition-all"
                style={{ width: `${pct}%` }}
              />
            </div>

            {state.phase === "disposition" && state.disposition && (
              <>
                <h2 className="mb-6 text-[1.15rem] font-semibold leading-relaxed text-text-primary">
                  {state.disposition.prompt}
                </h2>
                <div className="flex flex-col gap-3">
                  {state.disposition.options.map((opt, i) => (
                    <button
                      key={i}
                      type="button"
                      disabled={busy}
                      onClick={() => void submitAnswer({ choice_index: i })}
                      className="rounded-xl border border-border-primary px-5 py-4 text-left text-[0.95rem] text-text-primary transition-all hover:border-accent hover:bg-accent/[0.02] disabled:opacity-60"
                    >
                      {opt}
                    </button>
                  ))}
                </div>
              </>
            )}

            {state.phase === "probe" && state.probe && (
              <>
                <p className="mb-2 text-[0.8rem] font-semibold text-text-tertiary">
                  {state.probe.concept_name} — 같은 내용, 두 가지 설명
                </p>
                <h2 className="mb-4 text-[1.05rem] font-semibold text-text-primary">
                  어느 쪽이 더 와닿나요?
                </h2>
                <div className="flex flex-col gap-4">
                  {[
                    { label: "A · 비유·예시형", text: state.probe.variant_a, idx: 0 },
                    { label: "B · 정의·원리형", text: state.probe.variant_b, idx: 1 },
                  ].map(({ label, text, idx }) => (
                    <button
                      key={idx}
                      type="button"
                      disabled={busy}
                      onClick={() => void submitAnswer({ choice_index: idx })}
                      className="rounded-xl border border-border-primary p-5 text-left transition-all hover:border-accent hover:bg-accent/[0.02] disabled:opacity-60"
                    >
                      <span className="mb-2 block text-[0.8rem] font-semibold text-accent">
                        {label}
                      </span>
                      <span className="whitespace-pre-wrap text-[0.92rem] leading-relaxed text-text-secondary">
                        {text}
                      </span>
                    </button>
                  ))}
                </div>
              </>
            )}

            {state.phase === "quiz" && state.last_reveal && (
              <div
                className={clsx(
                  "mb-6 rounded-xl border px-4 py-3 text-[0.9rem]",
                  state.last_reveal.correct
                    ? "border-[#10b981]/40 bg-[#10b981]/10 text-[#047857]"
                    : "border-[#ef4444]/40 bg-[#ef4444]/10 text-[#b91c1c]",
                )}
              >
                <span className="font-semibold">
                  {state.last_reveal.correct ? "✅ 정답이에요!" : "❌ 오답이에요."}
                </span>
                {!state.last_reveal.correct && state.last_reveal.correct_answer && (
                  <span className="ml-1 text-text-secondary">
                    정답: {state.last_reveal.correct_answer}
                  </span>
                )}
              </div>
            )}

            {state.phase === "quiz" && state.question && (
              <QuizPanel
                key={state.question.id}
                question={state.question}
                busy={busy}
                errorMsg={errorMsg}
                onSubmit={(input) => void submitAnswer(input)}
              />
            )}

            {(state.phase === "disposition" || state.phase === "probe") && busy && (
              <p className="mt-4 flex items-center gap-2 text-[0.9rem] text-text-tertiary">
                <Spinner /> 다음 단계를 준비하고 있어요…
              </p>
            )}
          </>
        )}
      </div>
    </div>
  );
}
