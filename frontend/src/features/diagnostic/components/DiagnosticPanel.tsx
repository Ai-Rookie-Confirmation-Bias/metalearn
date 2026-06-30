// [3단계] 순수 UI. queries만 호출. BKT 진단 루프(시작→문항→채점→다음)를 구동.
// 문항 유형별 렌더: mcq=보기 버튼 / cloze·inverse=텍스트 인출 입력.
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { Button } from "@/shared/ui/Button";
import { useFlowStore } from "@/shared/store/flowStore";
import { apiErrorMessage } from "@/shared/api/errors";
import type { AnswerInput } from "@/features/diagnostic/api/diagnosticApi";
import {
  useStartDiagnostic,
  useSubmitAnswer,
} from "@/features/diagnostic/queries/useDiagnostic";
import type {
  AnswerResult,
  MasteryOut,
  Progress,
  QuestionOut,
  QuestionType,
  SessionState,
} from "@/features/diagnostic/types";

const QTYPE_LABEL: Record<QuestionType, string> = {
  mcq: "4지선다",
  cloze: "빈칸 인출",
  inverse: "역질문 인출",
};

/** 진단 완료 후 커리큘럼 대상: 가장 약한(모름) 개념 우선, 없으면 p_known 최저. */
function pickWeakestForCurriculum(masteries: MasteryOut[]): number {
  const unknown = masteries.filter((m) => m.resolved && m.p_known < 0.5);
  const pool = unknown.length > 0 ? unknown : masteries;
  return [...pool].sort((a, b) => a.p_known - b.p_known)[0].concept_id;
}

function MasteryBadge({
  m,
  onCurriculum,
}: {
  m: MasteryOut;
  onCurriculum: (conceptId: number) => void;
}) {
  const pct = Math.round(m.p_known * 100);
  let label = `측정 중 ${pct}%`;
  let color = "#888";
  if (m.resolved && m.p_known >= 0.5) {
    label = `앎 ${pct}%`;
    color = "#16a34a";
  } else if (m.resolved) {
    label = `모름 ${pct}%`;
    color = "#dc2626";
  }
  return (
    <li
      style={{
        padding: "4px 0",
        borderBottom: "1px solid #f0f0f0",
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        gap: 8,
      }}
    >
      <span>
        <span style={{ color, fontWeight: 600 }}>●</span> {m.concept_name}{" "}
        <span style={{ color, fontSize: 12 }}>
          [{label} · {m.answered_count}문항]
        </span>
      </span>
      <button
        onClick={() => onCurriculum(m.concept_id)}
        title="이 개념의 JIT 커리큘럼 생성"
        style={{
          fontSize: 11,
          padding: "2px 6px",
          cursor: "pointer",
          whiteSpace: "nowrap",
        }}
      >
        커리큘럼
      </button>
    </li>
  );
}

export function DiagnosticPanel() {
  const flowMaterialId = useFlowStore((s) => s.materialId);
  const setFlowSession = useFlowStore((s) => s.setSession);
  const setFlowConcept = useFlowStore((s) => s.setConcept);
  const setAutoGenerateCurriculum = useFlowStore((s) => s.setAutoGenerateCurriculum);
  const navigate = useNavigate();

  const [materialId, setMaterialId] = useState(
    flowMaterialId ? String(flowMaterialId) : "",
  );
  const [sessionId, setSessionId] = useState<number | null>(null);
  const [question, setQuestion] = useState<QuestionOut | null>(null);
  const [masteries, setMasteries] = useState<MasteryOut[]>([]);
  const [progress, setProgress] = useState<Progress>({ total: 0, resolved: 0 });
  const [done, setDone] = useState(false);
  const [feedback, setFeedback] = useState<AnswerResult | null>(null);
  const [text, setText] = useState("");

  const start = useStartDiagnostic();
  const answer = useSubmitAnswer();

  function applyState(s: SessionState) {
    setSessionId(s.session_id);
    setFlowSession(s.session_id);
    setQuestion(s.question);
    setMasteries(s.masteries);
    setProgress(s.progress);
    setDone(s.done);
    setFeedback(null);
    setText("");
  }

  function goCurriculum(conceptId: number) {
    setFlowConcept(conceptId);
    navigate("/lab/curriculum");
  }

  function handleStart() {
    const id = Number(materialId);
    if (!id) return;
    start.mutate(id, { onSuccess: applyState });
  }

  function submit(input: AnswerInput) {
    if (!sessionId || !question || answer.isPending) return;
    answer.mutate(
      { sessionId, questionId: question.id, input },
      {
        onSuccess: (r) => {
          setFeedback(r);
          setProgress(r.progress);
          setMasteries((prev) => {
            const updated = prev.map((m) =>
              m.concept_id === r.mastery.concept_id ? r.mastery : m,
            );
            if (r.done && sessionId) {
              const targetId = pickWeakestForCurriculum(updated);
              setFlowConcept(targetId);
              setAutoGenerateCurriculum(true);
              navigate("/lab/curriculum");
            }
            return updated;
          });
          setDone(r.done);
          setQuestion(r.next_question);
          setText("");
        },
      },
    );
  }

  if (sessionId === null) {
    return (
      <div>
        <input
          value={materialId}
          onChange={(e) => setMaterialId(e.target.value)}
          placeholder="자료 ID (Material #)"
          inputMode="numeric"
        />
        <Button
          onClick={handleStart}
          disabled={!materialId || start.isPending}
          style={{ marginLeft: 8 }}
        >
          {start.isPending ? "세션 생성 + 첫 문항..." : "정밀 진단 시작"}
        </Button>
        {start.error && (
          <p style={{ color: "crimson" }}>실패: {apiErrorMessage(start.error)}</p>
        )}
      </div>
    );
  }

  const busy = answer.isPending;

  return (
    <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 24 }}>
      <div>
        <p style={{ color: "#666" }}>
          확정 {progress.resolved} / {progress.total} 개념
        </p>

        {feedback && (
          <div
            style={{
              padding: 10,
              borderRadius: 6,
              background: feedback.is_correct ? "#ecfdf5" : "#fef2f2",
              color: feedback.is_correct ? "#065f46" : "#991b1b",
              marginBottom: 12,
            }}
          >
            <div>
              {feedback.is_correct ? "정답" : "오답"}
              {feedback.correct_answer && !feedback.is_correct && (
                <> · 모범답안: {feedback.correct_answer}</>
              )}
            </div>
            {feedback.explanation && (
              <div style={{ fontSize: 13, marginTop: 4 }}>{feedback.explanation}</div>
            )}
          </div>
        )}

        {done && (
          <div style={{ padding: 12, background: "#f0f9ff", borderRadius: 6 }}>
            <strong>진단 완료.</strong> 모든 개념의 신뢰도가 경계(앎/모름)로 확정됐습니다.
          </div>
        )}

        {!done && question && (
          <div>
            <p style={{ fontSize: 12, color: "#2563eb" }}>
              대상 개념: {question.concept_name} · 유형: {QTYPE_LABEL[question.qtype]}
            </p>
            <h3 style={{ marginTop: 4, whiteSpace: "pre-wrap" }}>{question.question}</h3>

            {question.qtype === "mcq" ? (
              <div style={{ display: "grid", gap: 8, marginTop: 12 }}>
                {question.options.map((opt, idx) => (
                  <Button
                    key={idx}
                    onClick={() => submit({ selected_index: idx })}
                    disabled={busy}
                    style={{ textAlign: "left" }}
                  >
                    {String.fromCharCode(65 + idx)}. {opt}
                  </Button>
                ))}
              </div>
            ) : (
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  if (text.trim()) submit({ answer_text: text.trim() });
                }}
                style={{ marginTop: 12, display: "flex", gap: 8 }}
              >
                <input
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  placeholder="직접 떠올려 입력 (인출)"
                  style={{ flex: 1, padding: "0.5rem" }}
                  autoFocus
                />
                <Button type="submit" disabled={busy || !text.trim()}>
                  제출
                </Button>
              </form>
            )}

            {busy && <p style={{ color: "#888" }}>채점 중...</p>}
            {answer.error && (
              <p style={{ color: "crimson" }}>실패: {apiErrorMessage(answer.error)}</p>
            )}
          </div>
        )}
      </div>

      <aside>
        <h4>개념별 숙련도</h4>
        <p style={{ fontSize: 12, color: "#888", marginTop: 0 }}>
          개념을 눌러 맞춤 커리큘럼을 생성하세요.
        </p>
        <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
          {masteries.map((m) => (
            <MasteryBadge key={m.concept_id} m={m} onCurriculum={goCurriculum} />
          ))}
        </ul>
      </aside>
    </div>
  );
}
