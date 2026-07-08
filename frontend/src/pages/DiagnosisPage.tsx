/**
 * 수준 진단 = 배치고사(Placement, ISSUE-015) — /diagnosis/:courseId.
 *   업로드 직후(또는 책장 CTA)에서 진입 → 배치고사 루프(문항 1개씩) → 완료 시
 *   커리큘럼 배치(placement) 시딩 후 책장으로.
 *
 * 구형 진단과 달리 문항별 정오답 피드백이 없다: 목적이 "수준 확정"이 아니라
 * 학습 시작 좌표(floor) 하나 찾기라, 답하면 바로 다음 문항으로 넘어간다
 * (평가 피로 최소화 — 설계방향). 정밀 판정은 학습 중 인출학습으로 이관.
 *
 * 서버가 진실: 다음 문항·종료 판정은 전부 서버 응답(PlacementState)으로만 갱신.
 * 씨앗(커리큘럼 트리)은 업로드 파이프라인이 이미 만들어 두므로 여기선 조립하지
 * 않고, 배치고사 종료 시 서버가 floor/ceiling·enrollment를 확정한다. 프론트는
 * 커리큘럼 배치(concept_mastery 시딩)만 한 번 호출한다.
 */
import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { clsx } from "clsx";
import { MagnifyingGlassIcon, WarningCircleIcon } from "@phosphor-icons/react";

import { apiErrorMessage } from "@/shared/api/errors";
import { startPlacement, answerPlacement } from "@/features/diagnostic/api/placementApi";
import { initPlacement } from "@/features/diagnostic/api/completionApi";
import type { QuestionOut, QuestionType } from "@/features/diagnostic/types";

const QTYPE_LABEL: Record<QuestionType, string> = {
  mcq: "선택형",
  cloze: "빈칸 채우기",
  inverse: "떠올려 쓰기",
};

type Phase =
  | "starting" // 세션 생성 + 첫 문항 생성 (수십 초 걸릴 수 있음)
  | "quiz" // 문항 풀이 루프
  | "finalizing" // 커리큘럼 배치 시딩
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
  const navigate = useNavigate();

  const [phase, setPhase] = useState<Phase>("starting");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [question, setQuestion] = useState<QuestionOut | null>(null);
  const [asked, setAsked] = useState(0); // 지금까지 답한 문항 수
  const [maxQuestions, setMaxQuestions] = useState(12);
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
      const s = await startPlacement(courseId);
      setSessionId(s.session_id);
      setMaxQuestions(s.max_questions);
      setAsked(s.asked);
      if (s.done || !s.question) {
        // 물을 문항이 없으면(대표 개념 부족 등) 바로 후처리로
        void finalize();
      } else {
        setQuestion(s.question);
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
      // 트리·floor/ceiling·enrollment는 배치고사 종료 시 서버가 이미 확정.
      // 여기선 커리큘럼 진행축 concept_mastery 시딩만 한다(학습 시작 지점).
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
      const s = await answerPlacement(sessionId, question.id, input);
      setAsked(s.asked);
      if (s.done || !s.question) {
        void finalize();
        return;
      }
      // 배치고사는 문항별 피드백 없이 바로 다음 문항으로.
      setQuestion(s.question);
      setPicked(null);
      setText("");
    } catch (e) {
      setErrorMsg(apiErrorMessage(e));
      setPicked(null);
    } finally {
      setBusy(false);
    }
  }

  // 진행 표시 — 현재 문항 번호(= 지금까지 답한 수 + 1)와 상한.
  const questionNo = Math.min(maxQuestions, asked + 1);
  const pct = maxQuestions > 0 ? Math.round((asked / maxQuestions) * 100) : 0;

  return (
    <div className="flex min-h-screen items-center justify-center bg-bg-secondary px-4 py-10">
      <div className="w-full max-w-[720px] rounded-2xl border border-border-primary bg-white p-12 shadow-lg max-[480px]:p-6">
        {phase === "starting" && (
          <CenterNotice
            icon={<Spinner className="h-9 w-9 border-[3px]" />}
            title="배치고사를 준비하고 있어요"
            desc={
              "자료의 개념들로 맞춤 문항을 준비 중이에요.\n최대 1~2분 정도 걸릴 수 있어요. 화면을 닫지 말고 잠시만 기다려주세요."
            }
          />
        )}

        {phase === "start_error" && (
          <CenterNotice
            icon={<WarningCircleIcon className="text-[3rem] text-red-500" />}
            title="배치고사를 시작하지 못했어요"
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
            title="배치 완료! 커리큘럼을 준비하고 있어요"
            desc={
              "배치고사 결과로 학습 시작 지점을 정하고\n나만의 커리큘럼 뼈대를 만드는 중이에요. 곧 책장으로 이동해요."
            }
          />
        )}

        {phase === "finalize_error" && (
          <CenterNotice
            icon={<WarningCircleIcon className="text-[3rem] text-red-500" />}
            title="커리큘럼 준비에 실패했어요"
            desc={`배치고사 결과는 저장돼 있어요. 다시 시도하면 이어서 처리돼요.\n\n${errorMsg ?? ""}`}
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
            {/* 진행 헤더: 문항 기준 (배치고사는 최대 상한까지, 조기 종료 가능) */}
            <div className="mb-2 flex items-center justify-between">
              <span className="flex items-center gap-1.5 text-sm font-semibold text-accent">
                <MagnifyingGlassIcon /> 배치고사
              </span>
              <span className="text-[0.85rem] font-semibold text-text-secondary">
                문항 {questionNo}번째 · 최대 {maxQuestions}문항
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
                  // 배치고사는 정오답을 노출하지 않는다 — 선택 표시만(제출 중 하이라이트).
                  const isPicked = picked === i;
                  return (
                    <button
                      key={i}
                      type="button"
                      disabled={busy}
                      onClick={() => {
                        setPicked(i);
                        void submit({ selected_index: i });
                      }}
                      className={clsx(
                        "flex items-center gap-4 rounded-xl border px-5 py-4 text-left text-[0.95rem] transition-all",
                        isPicked
                          ? "border-accent bg-accent/[0.06] font-semibold text-text-primary"
                          : "border-border-primary bg-white text-text-primary hover:border-accent hover:bg-accent/[0.02]",
                        busy && "cursor-default",
                      )}
                    >
                      <span
                        className={clsx(
                          "flex h-6 w-6 shrink-0 items-center justify-center rounded-full border text-[0.8rem] font-bold",
                          isPicked
                            ? "border-accent bg-accent text-white"
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
                  if (text.trim() && !busy) void submit({ answer_text: text.trim() });
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
                <Spinner /> 다음 문항을 준비하고 있어요…
              </p>
            )}
            {errorMsg && !busy && (
              <p className="mt-4 text-[0.9rem] text-red-600">
                제출 실패: {errorMsg} — 다시 시도해주세요.
              </p>
            )}
          </>
        )}
      </div>
    </div>
  );
}
