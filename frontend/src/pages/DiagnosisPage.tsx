/**
 * 수준 진단(Diagnosis) — /diagnosis/:courseId. 셸 없는 전체화면 집중 플로우.
 *   업로드 직후(또는 책장 CTA)에서 진입 → BKT 진단 루프 → 완료 시
 *   씨앗 조립(seed build) + 수준 배치(placement) 후 책장으로.
 * 서버가 진실: 문항·채점·다음 문항 전부 서버 응답(AnswerResult)으로만 갱신.
 *   오답 시 하위(선수) 개념 문항이 새로 열리는 것도 progress.total 증가로 반영됨.
 * UI는 학습 화면 McqBlock과 같은 디자인 언어(선택지 버튼·정오답 색)를 따른다.
 */
import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { clsx } from "clsx";
import { ArrowRightIcon, MagnifyingGlassIcon, WarningCircleIcon } from "@phosphor-icons/react";

import { apiErrorMessage } from "@/shared/api/errors";
import { startDiagnostic, submitAnswer } from "@/features/diagnostic/api/diagnosticApi";
import { buildSeed, initPlacement } from "@/features/diagnostic/api/completionApi";
import type {
  AnswerResult,
  Progress,
  QuestionOut,
  QuestionType,
} from "@/features/diagnostic/types";

const QTYPE_LABEL: Record<QuestionType, string> = {
  mcq: "선택형",
  cloze: "빈칸 채우기",
  inverse: "떠올려 쓰기",
};

type Phase =
  | "starting" // 세션 생성 + 전 문항 배치 생성 (수십 초 걸릴 수 있음)
  | "quiz" // 문항 풀이 루프
  | "finalizing" // 씨앗 조립 + 배치
  | "start_error"
  | "finalize_error";

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

// 전체화면 안내 패널 (시작 대기 / 완료 처리 / 에러 공통)
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
      <p className="max-w-[400px] whitespace-pre-line text-[0.95rem] leading-relaxed text-text-secondary">
        {desc}
      </p>
      {action && <div className="mt-8">{action}</div>}
    </div>
  );
}

export function DiagnosisPage() {
  const { courseId } = useParams<{ courseId: string }>();
  const [searchParams] = useSearchParams();
  // 수업 생성 STEP 3에서 고른 학습 목표 — 씨앗 조립(purpose)으로 전달
  const purpose = searchParams.get("purpose") ?? undefined;
  const navigate = useNavigate();

  const [phase, setPhase] = useState<Phase>("starting");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [question, setQuestion] = useState<QuestionOut | null>(null);
  const [progress, setProgress] = useState<Progress>({ total: 0, resolved: 0 });
  const [feedback, setFeedback] = useState<AnswerResult | null>(null);
  const [pendingNext, setPendingNext] = useState<QuestionOut | null>(null);
  const [picked, setPicked] = useState<number | null>(null);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const startedRef = useRef(false); // StrictMode 이중 실행 가드

  async function start() {
    if (!courseId) return;
    setPhase("starting");
    setErrorMsg(null);
    try {
      const s = await startDiagnostic(courseId);
      setSessionId(s.session_id);
      setQuestion(s.question);
      setProgress(s.progress);
      if (s.done) {
        // 확정할 개념이 없으면(이미 전부 resolved) 바로 후처리로
        void finalize();
      } else {
        setPhase("quiz");
      }
    } catch (e) {
      setErrorMsg(apiErrorMessage(e));
      setPhase("start_error");
    }
  }

  async function finalize() {
    if (!courseId) return;
    setPhase("finalizing");
    setErrorMsg(null);
    try {
      // 순서 고정: 씨앗(트리+enrollment) → 배치(mastery 시딩). 서버 계약과 동일.
      await buildSeed(courseId, purpose);
      await initPlacement(courseId);
      navigate("/library");
    } catch (e) {
      setErrorMsg(apiErrorMessage(e));
      setPhase("finalize_error");
    }
  }

  useEffect(() => {
    if (startedRef.current) return;
    startedRef.current = true;
    void start();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function submit(input: { selected_index?: number; answer_text?: string }) {
    if (!sessionId || !question || busy) return;
    setBusy(true);
    setErrorMsg(null);
    try {
      const r = await submitAnswer(sessionId, question.id, input);
      setFeedback(r);
      setProgress(r.progress); // 오답으로 하위 개념이 열리면 total이 늘어남
      setPendingNext(r.next_question);
    } catch (e) {
      setErrorMsg(apiErrorMessage(e));
      setPicked(null);
    } finally {
      setBusy(false);
    }
  }

  // 해설 확인 후 다음 문항으로 (전 문항 확정이면 후처리 시작)
  function goNext() {
    if (!feedback) return;
    if (feedback.done) {
      void finalize();
      return;
    }
    setQuestion(pendingNext);
    setFeedback(null);
    setPendingNext(null);
    setPicked(null);
    setText("");
  }

  // 문항 기준 진행 표시 — total(코스 전체 개념 수)을 문항 수로 오해하는 문제 방지.
  // 신규 필드가 없는 구응답이면 기존 '개념 확정' 표시로 폴백한다.
  const answered = progress.answered_questions ?? null;
  const cap = progress.question_cap ?? null;
  const byQuestion = answered !== null && cap !== null && cap > 0;
  // 채점 직후(feedback 표시 중)엔 answered에 방금 문항이 이미 포함돼 있어
  // +1 하면 번호가 미리 튀므로, 현재 문항 번호를 그대로 유지한다.
  const questionNo = byQuestion ? Math.min(cap, feedback ? answered : answered + 1) : 0;
  const pct = byQuestion
    ? Math.round((Math.min(answered, cap) / cap) * 100)
    : progress.total > 0
      ? Math.round((progress.resolved / progress.total) * 100)
      : 0;

  return (
    <div className="flex min-h-screen items-center justify-center bg-bg-secondary px-4 py-10">
      <div className="w-full max-w-[720px] rounded-2xl border border-border-primary bg-white p-12 shadow-lg max-[480px]:p-6">
        {phase === "starting" && (
          <CenterNotice
            icon={<Spinner className="h-9 w-9 border-[3px]" />}
            title="진단 문항을 만들고 있어요"
            desc={
              "자료의 개념들로 맞춤 문항을 준비 중이에요.\n최대 1~2분 정도 걸릴 수 있어요. 화면을 닫지 말고 잠시만 기다려주세요."
            }
          />
        )}

        {phase === "start_error" && (
          <CenterNotice
            icon={<WarningCircleIcon className="text-[3rem] text-red-500" />}
            title="진단을 시작하지 못했어요"
            desc={errorMsg ?? "알 수 없는 오류가 발생했어요."}
            action={
              <div className="flex gap-3">
                <button
                  onClick={() => void start()}
                  className="rounded-xl bg-primary px-6 py-3 text-[0.9rem] font-semibold text-white transition-colors hover:bg-primary-hover"
                >
                  다시 시도
                </button>
                <button
                  onClick={() => navigate("/library")}
                  className="rounded-xl border border-border-primary px-6 py-3 text-[0.9rem] font-semibold text-text-secondary transition-colors hover:bg-bg-secondary"
                >
                  책장으로
                </button>
              </div>
            }
          />
        )}

        {phase === "finalizing" && (
          <CenterNotice
            icon={<Spinner className="h-9 w-9 border-[3px]" />}
            title="진단 완료! 커리큘럼을 준비하고 있어요"
            desc={
              "진단 결과로 학습 시작 지점을 정하고\n나만의 커리큘럼 뼈대를 만드는 중이에요. 곧 책장으로 이동해요."
            }
          />
        )}

        {phase === "finalize_error" && (
          <CenterNotice
            icon={<WarningCircleIcon className="text-[3rem] text-red-500" />}
            title="커리큘럼 준비에 실패했어요"
            desc={`진단 결과는 저장돼 있어요. 다시 시도하면 이어서 처리돼요.\n\n${errorMsg ?? ""}`}
            action={
              <button
                onClick={() => void finalize()}
                className="rounded-xl bg-primary px-6 py-3 text-[0.9rem] font-semibold text-white transition-colors hover:bg-primary-hover"
              >
                다시 시도
              </button>
            }
          />
        )}

        {phase === "quiz" && question && (
          <>
            {/* 진행 헤더: 문항 기준 (구응답엔 필드가 없어 개념 확정 표시로 폴백) */}
            <div className="mb-2 flex items-center justify-between">
              <span className="flex items-center gap-1.5 text-sm font-semibold text-accent">
                <MagnifyingGlassIcon /> 수준 진단
              </span>
              <span className="text-[0.85rem] font-semibold text-text-secondary">
                {byQuestion
                  ? `문항 ${questionNo}번째 · 최대 ${cap}문항`
                  : `개념 확정 ${progress.resolved} / ${progress.total}`}
              </span>
            </div>
            <div className="mb-8 h-1.5 w-full overflow-hidden rounded-full bg-bg-secondary">
              <div
                className="h-full rounded-full bg-accent transition-all"
                style={{ width: `${pct}%` }}
              />
            </div>

            <p className="mb-2 text-[0.8rem] font-semibold text-text-tertiary">
              {question.concept_name} · {QTYPE_LABEL[question.qtype]}
            </p>
            <h2 className="mb-6 whitespace-pre-wrap text-[1.15rem] font-semibold leading-relaxed text-text-primary">
              {question.question}
            </h2>

            {question.qtype === "mcq" ? (
              <div className="flex flex-col gap-3">
                {question.options.map((opt, i) => {
                  // 채점 후: 내가 고른 것 + 실제 정답을 색으로 표시 (McqBlock과 동일 언어)
                  const isPicked = picked === i;
                  const isAnswer = feedback?.correct_index === i;
                  const state = !feedback
                    ? "idle"
                    : isAnswer
                      ? "correct"
                      : isPicked
                        ? "incorrect"
                        : "dim";
                  return (
                    <button
                      key={i}
                      type="button"
                      disabled={busy || !!feedback}
                      onClick={() => {
                        setPicked(i);
                        void submit({ selected_index: i });
                      }}
                      className={clsx(
                        "flex items-center gap-4 rounded-xl border px-5 py-4 text-left text-[0.95rem] transition-all",
                        state === "idle" &&
                          "border-border-primary bg-white text-text-primary hover:border-accent hover:bg-accent/[0.02]",
                        state === "correct" &&
                          "border-[#10b981] bg-[#10b981]/10 font-semibold text-[#047857]",
                        state === "incorrect" && "border-[#ef4444] bg-[#ef4444]/10 text-[#b91c1c]",
                        state === "dim" && "border-border-primary bg-white text-text-tertiary",
                        feedback && "cursor-default",
                      )}
                    >
                      <span
                        className={clsx(
                          "flex h-6 w-6 shrink-0 items-center justify-center rounded-full border text-[0.8rem] font-bold",
                          state === "correct"
                            ? "border-[#10b981] bg-[#10b981] text-white"
                            : state === "incorrect"
                              ? "border-[#ef4444] text-[#b91c1c]"
                              : "border-border-primary text-text-tertiary",
                        )}
                      >
                        {String.fromCharCode(65 + i)}
                      </span>
                      <span>{opt}</span>
                    </button>
                  );
                })}
              </div>
            ) : (
              // 인출형(cloze/inverse): 보기 없이 직접 떠올려 쓰기 — 진단 정확도의 핵심
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  if (text.trim() && !feedback) void submit({ answer_text: text.trim() });
                }}
                className="flex gap-2"
              >
                <input
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  disabled={busy || !!feedback}
                  placeholder="정답을 직접 떠올려 입력해주세요"
                  autoFocus
                  className="flex-1 rounded-xl border border-border-primary bg-white px-4 py-3 text-[0.95rem] text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none disabled:bg-bg-secondary"
                />
                <button
                  type="submit"
                  disabled={busy || !text.trim() || !!feedback}
                  className="shrink-0 rounded-xl bg-primary px-6 py-3 text-[0.9rem] font-semibold text-white transition-colors hover:bg-primary-hover disabled:cursor-not-allowed disabled:opacity-50"
                >
                  제출
                </button>
              </form>
            )}

            {busy && (
              <p className="mt-4 flex items-center gap-2 text-[0.9rem] text-text-tertiary">
                <Spinner /> 채점하고 있어요…
              </p>
            )}
            {errorMsg && !busy && (
              <p className="mt-4 text-[0.9rem] text-red-600">채점 실패: {errorMsg} — 다시 시도해주세요.</p>
            )}

            {/* 채점 결과 + 해설 → 확인 후 다음으로 (자동 넘김 대신 해설 읽을 시간 보장) */}
            {feedback && (
              <div
                className={clsx(
                  "mt-6 rounded-xl border px-5 py-4",
                  feedback.is_correct
                    ? "border-[#10b981]/40 bg-[#10b981]/5"
                    : "border-[#ef4444]/40 bg-[#ef4444]/5",
                )}
              >
                <div
                  className={clsx(
                    "font-bold",
                    feedback.is_correct ? "text-[#047857]" : "text-[#b91c1c]",
                  )}
                >
                  {feedback.is_correct ? "정답이에요!" : "아쉬워요"}
                  {!feedback.is_correct && feedback.correct_answer && (
                    <span className="ml-2 font-medium text-text-secondary">
                      모범답안: {feedback.correct_answer}
                    </span>
                  )}
                </div>
                {feedback.explanation && (
                  <p className="mt-1.5 text-[0.9rem] leading-relaxed text-text-secondary">
                    {feedback.explanation}
                  </p>
                )}
                <button
                  onClick={goNext}
                  autoFocus
                  className="mt-4 inline-flex items-center gap-2 rounded-xl bg-primary px-5 py-2.5 text-[0.9rem] font-semibold text-white transition-all hover:-translate-y-0.5 hover:bg-primary-hover"
                >
                  {feedback.done ? "진단 마치기" : "다음 문항"} <ArrowRightIcon />
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
