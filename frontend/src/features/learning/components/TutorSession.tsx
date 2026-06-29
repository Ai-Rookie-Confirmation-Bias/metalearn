import { useMutation } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";

import {
  completeSession,
  getHint,
  startSession,
  submitResponse,
} from "@/features/learning/api/learningApi";
import type { HintResponse, RespondResponse } from "@/features/learning/types";
import { GenerationBanner } from "@/features/seed/components/GenerationBanner";
import { UnitContent } from "@/features/seed/components/UnitContent";
import type { CurriculumUnit } from "@/features/seed/types";
import { Button } from "@/shared/ui/Button";

type Phase = "learn" | "check";

interface Props {
  profileId: string;
  unit: CurriculumUnit;
  onComplete: () => void;
}

function getErrorMessage(err: unknown): string {
  if (err && typeof err === "object" && "response" in err) {
    const res = (err as { response?: { data?: { detail?: unknown } } }).response;
    const detail = res?.data?.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) return detail.map((d) => JSON.stringify(d)).join(", ");
  }
  if (err instanceof Error) return err.message;
  return "요청에 실패했습니다.";
}

function PhaseLabel({ step, label }: { step: 1 | 2; label: string }) {
  return (
    <span
      style={{
        display: "inline-block",
        marginBottom: "0.75rem",
        padding: "0.25rem 0.65rem",
        borderRadius: 6,
        fontSize: "0.78rem",
        fontWeight: 700,
        background: step === 1 ? "#f0f4ff" : "#eef6ff",
        color: "#4a90e2",
        border: "1px solid #c5d9f7",
      }}
    >
      {step}단계 · {label}
    </span>
  );
}

function AiBubble({ children }: { children: ReactNode }) {
  return (
    <div style={{ display: "flex", gap: "0.75rem", alignItems: "flex-start", marginBottom: "1rem" }}>
      <span
        aria-hidden
        style={{
          width: 32,
          height: 32,
          borderRadius: "50%",
          background: "#4a90e2",
          color: "#fff",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: "0.85rem",
          flexShrink: 0,
        }}
      >
        AI
      </span>
      <div
        style={{
          flex: 1,
          padding: "0.85rem 1rem",
          background: "#eef6ff",
          border: "1px solid #99c2ff",
          borderRadius: "12px 12px 12px 4px",
          fontSize: "0.92rem",
          lineHeight: 1.65,
          color: "#222",
          whiteSpace: "pre-wrap",
        }}
      >
        {children}
      </div>
    </div>
  );
}

function StatusBadge({ variant, label }: { variant: "success" | "error"; label: string }) {
  const isSuccess = variant === "success";
  return (
    <span
      style={{
        display: "inline-block",
        marginBottom: "0.75rem",
        padding: "0.35rem 0.75rem",
        borderRadius: 999,
        fontSize: "0.82rem",
        fontWeight: 700,
        background: isSuccess ? "#e6f7ed" : "#fdecea",
        color: isSuccess ? "#1a7f37" : "#c0392b",
        border: `1px solid ${isSuccess ? "#9dd9b4" : "#f5b7b1"}`,
      }}
    >
      {label}
    </span>
  );
}

function LoadingOverlay({ message = "AI가 분석 중..." }: { message?: string }) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: "0.75rem",
        padding: "0.85rem 1rem",
        marginBottom: "1rem",
        background: "#f8faff",
        borderRadius: 8,
        border: "1px solid #dde8ff",
        color: "#4a5568",
        fontSize: "0.9rem",
      }}
    >
      <span
        aria-hidden
        style={{
          width: 18,
          height: 18,
          border: "2px solid #99c2ff",
          borderTopColor: "#4a90e2",
          borderRadius: "50%",
          display: "inline-block",
          animation: "tutor-spin 0.8s linear infinite",
        }}
      />
      {message}
      <style>{`@keyframes tutor-spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}

function LearnPhase({
  unit,
  onStartCheck,
  isStarting,
}: {
  unit: CurriculumUnit;
  onStartCheck: () => void;
  isStarting: boolean;
}) {
  return (
    <div>
      <PhaseLabel step={1} label="학습" />
      <GenerationBanner mode="llm" note="Solar가 생성한 단원 설명을 먼저 읽어 보세요." />

      {unit.focus && (
        <p
          style={{
            margin: "0 0 0.75rem",
            padding: "0.5rem 0.75rem",
            background: "#fff8e6",
            borderRadius: 6,
            fontSize: "0.85rem",
            color: "#7a5a00",
            borderLeft: "3px solid #f5a623",
          }}
        >
          <strong>학습 포인트</strong> · {unit.focus}
        </p>
      )}

      {unit.content ? (
        <UnitContent content={unit.content} />
      ) : (
        <p style={{ color: "#888", fontSize: "0.88rem", margin: "0.5rem 0 1rem" }}>
          설명 콘텐츠가 없습니다. 아래 버튼으로 바로 확인 문제에 도전할 수 있습니다.
        </p>
      )}

      {isStarting ? (
        <LoadingOverlay message="Solar 튜터가 확인 문제를 준비 중..." />
      ) : (
        <Button style={{ marginTop: "1rem" }} onClick={onStartCheck}>
          이해했어요 · 확인 문제 풀기
        </Button>
      )}
    </div>
  );
}

export function TutorSession({ profileId, unit, onComplete }: Props) {
  const [phase, setPhase] = useState<Phase>("learn");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [question, setQuestion] = useState<string | null>(null);
  const [userResponse, setUserResponse] = useState("");
  const [respondResult, setRespondResult] = useState<RespondResponse | null>(null);
  const [extraHints, setExtraHints] = useState<HintResponse[]>([]);
  const [error, setError] = useState<string | null>(null);

  const startMutation = useMutation({
    mutationFn: () => startSession(profileId, unit.order),
    onSuccess: (data) => {
      setError(null);
      setSessionId(data.session_id);
      setQuestion(data.question);
      setPhase("check");
    },
    onError: (err) => setError(getErrorMessage(err)),
  });

  const respondMutation = useMutation({
    mutationFn: (response: string) => {
      if (!sessionId) throw new Error("세션이 시작되지 않았습니다.");
      return submitResponse(sessionId, response);
    },
    onSuccess: (data) => {
      setError(null);
      setRespondResult(data);
    },
    onError: (err) => setError(getErrorMessage(err)),
  });

  const hintMutation = useMutation({
    mutationFn: () => {
      if (!sessionId) throw new Error("세션이 시작되지 않았습니다.");
      return getHint(sessionId);
    },
    onSuccess: (data) => {
      setError(null);
      setExtraHints((prev) => {
        if (prev.some((h) => h.step_type === data.step_type)) return prev;
        return [...prev, data];
      });
    },
    onError: (err) => setError(getErrorMessage(err)),
  });

  const completeMutation = useMutation({
    mutationFn: () => {
      if (!sessionId) throw new Error("세션이 시작되지 않았습니다.");
      return completeSession(sessionId);
    },
    onSuccess: () => {
      setError(null);
      onComplete();
    },
    onError: (err) => setError(getErrorMessage(err)),
  });

  const isLoading =
    startMutation.isPending ||
    respondMutation.isPending ||
    hintMutation.isPending ||
    completeMutation.isPending;

  const hasHint2 = extraHints.some((h) => h.step_type === "hint_2");
  const answerReveal = extraHints.find((h) => h.step_type === "answer_reveal");
  const showQuestionInput = phase === "check" && question && !respondResult && !isLoading;
  const showIncorrectActions = respondResult?.correct === false && !answerReveal;

  const handleFinish = () => {
    if (!sessionId) {
      onComplete();
      return;
    }
    completeMutation.mutate();
  };

  return (
    <div style={{ padding: "0.75rem 1rem 1rem", borderTop: "1px solid #e8ecf4" }}>
      {phase === "learn" && (
        <LearnPhase
          unit={unit}
          onStartCheck={() => startMutation.mutate()}
          isStarting={startMutation.isPending}
        />
      )}

      {phase === "check" && (
        <>
          <PhaseLabel step={2} label="확인" />
          <GenerationBanner mode="llm" note="Solar 튜터 · 역질문 · 힌트 · 정답 해설" />

          {isLoading && !respondResult && <LoadingOverlay />}

          {question && (
            <AiBubble>
              <strong style={{ display: "block", marginBottom: 4, color: "#4a90e2" }}>
                {unit.title} — 역질문
              </strong>
              {question}
            </AiBubble>
          )}

          {showQuestionInput && (
            <div style={{ marginBottom: "1rem" }}>
              <textarea
                value={userResponse}
                onChange={(e) => setUserResponse(e.target.value)}
                placeholder="학습 내용을 바탕으로 생각을 적어 보세요..."
                rows={3}
                style={{
                  width: "100%",
                  padding: "0.65rem 0.75rem",
                  borderRadius: 8,
                  border: "1px solid #ccc",
                  fontSize: "0.92rem",
                  resize: "vertical",
                  boxSizing: "border-box",
                }}
              />
              <Button
                style={{ marginTop: "0.5rem" }}
                disabled={!userResponse.trim() || respondMutation.isPending}
                onClick={() => respondMutation.mutate(userResponse.trim())}
              >
                제출
              </Button>
            </div>
          )}

          {respondResult?.correct === true && (
            <div style={{ marginBottom: "1rem" }}>
              <StatusBadge variant="success" label="정답입니다" />
              <p style={{ margin: "0 0 1rem", lineHeight: 1.65, color: "#333" }}>
                {respondResult.feedback}
              </p>
              <Button onClick={handleFinish} disabled={completeMutation.isPending}>
                {completeMutation.isPending ? "저장 중..." : "다음 단원"}
              </Button>
            </div>
          )}

          {respondResult?.correct === false && (
        <div style={{ marginBottom: "1rem" }}>
          <StatusBadge variant="error" label="다시 생각해보세요" />
          {"missing_concept" in respondResult && respondResult.missing_concept && (
            <p
              style={{
                margin: "0 0 0.75rem",
                padding: "0.5rem 0.75rem",
                background: "#fff5f5",
                borderRadius: 6,
                fontSize: "0.85rem",
                color: "#7a2e2e",
                borderLeft: "3px solid #e74c3c",
              }}
            >
              <strong>부족한 개념</strong> · {respondResult.missing_concept}
              {respondResult.reason && (
                <span style={{ display: "block", marginTop: 4, color: "#555" }}>
                  {respondResult.reason}
                </span>
              )}
            </p>
          )}
          <AiBubble>{respondResult.hint}</AiBubble>

              {extraHints.map((hint) => (
                <AiBubble key={hint.step_type}>
                  <strong style={{ display: "block", marginBottom: 4, color: "#4a90e2" }}>
                    {hint.step_type === "hint_2" ? "추가 힌트" : "정답 해설"}
                  </strong>
                  {hint.content}
                </AiBubble>
              ))}

              {showIncorrectActions && (
                <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
                  {!hasHint2 && (
                    <Button onClick={() => hintMutation.mutate()} disabled={hintMutation.isPending}>
                      힌트 더 보기
                    </Button>
                  )}
                  <Button onClick={() => hintMutation.mutate()} disabled={hintMutation.isPending}>
                    정답 보기
                  </Button>
                </div>
              )}

              {answerReveal && (
                <Button
                  style={{ marginTop: "0.75rem" }}
                  onClick={handleFinish}
                  disabled={completeMutation.isPending}
                >
                  {completeMutation.isPending ? "저장 중..." : "학습 마치기"}
                </Button>
              )}
            </div>
          )}
        </>
      )}

      {error && (
        <p style={{ color: "crimson", marginTop: "0.75rem" }}>
          {error}
          {phase === "learn" && !startMutation.isPending && (
            <Button
              style={{ marginLeft: "0.5rem" }}
              onClick={() => startMutation.mutate()}
              disabled={startMutation.isPending}
            >
              다시 시도
            </Button>
          )}
        </p>
      )}
    </div>
  );
}
