import { useEffect, useMemo, useState } from "react";

import { analyzePrerequisites } from "@/features/seed/api/seedApi";
import type {
  DocumentSkeleton,
  LearningGoal,
  LearningRange,
  PrerequisiteAnalysis,
  TocEntry,
} from "@/features/seed/types";
import { LEARNING_GOAL_LABELS, PREREQUISITE_LABELS } from "@/features/seed/types";
import { Button } from "@/shared/ui/Button";

interface Props {
  skeleton: DocumentSkeleton;
  onSubmit: (payload: {
    learning_range: LearningRange;
    known_before: string[];
    learning_goal: LearningGoal | null;
  }) => void;
  isPending: boolean;
  error: string | null;
}

function chaptersBefore(toc: TocEntry[], startId: string): TocEntry[] {
  const start = toc.find((t) => t.id === startId);
  if (!start) return [];
  return toc.filter((t) => t.end_page < start.start_page);
}

export function SurveyWizard({ skeleton, onSubmit, isPending, error }: Props) {
  const [step, setStep] = useState(1);
  const [rangeStart, setRangeStart] = useState(skeleton.toc[0]?.id ?? "");
  const [rangeEnd, setRangeEnd] = useState(skeleton.toc[skeleton.toc.length - 1]?.id ?? "");
  const [knownBefore, setKnownBefore] = useState<Set<string>>(new Set());
  const [goal, setGoal] = useState<LearningGoal | "">("");
  const [prereqAnalysis, setPrereqAnalysis] = useState<PrerequisiteAnalysis | null>(null);
  const [prereqLoading, setPrereqLoading] = useState(false);
  const [prereqError, setPrereqError] = useState<string | null>(null);

  const priorChapters = useMemo(
    () => chaptersBefore(skeleton.toc, rangeStart),
    [skeleton.toc, rangeStart],
  );

  useEffect(() => {
    if (step !== 2) return;

    let cancelled = false;
    setPrereqLoading(true);
    setPrereqError(null);

    analyzePrerequisites({
      document_id: skeleton.document_id,
      learning_range: { start: rangeStart, end: rangeEnd },
      known_before: [...knownBefore],
    })
      .then((data) => {
        if (!cancelled) setPrereqAnalysis(data);
      })
      .catch(() => {
        if (!cancelled) setPrereqError("선행지식 AI 분석 실패 — 아래 목록에서 직접 선택하세요.");
      })
      .finally(() => {
        if (!cancelled) setPrereqLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [step, skeleton.document_id, rangeStart, rangeEnd]);

  const toggleKnown = (id: string) => {
    setKnownBefore((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleFinalSubmit = () => {
    onSubmit({
      learning_range: { start: rangeStart, end: rangeEnd },
      known_before: [...knownBefore],
      learning_goal: goal || null,
    });
  };

  const aiSuggestions = prereqAnalysis?.suggestions ?? [];
  const staticChapterIds = new Set(priorChapters.map((t) => t.id));
  const staticExtIds = new Set(skeleton.external_prerequisites);
  const aiOnlySuggestions = aiSuggestions.filter((s) => {
    if (s.source === "in_document") return !staticChapterIds.has(s.id);
    return !staticExtIds.has(s.id);
  });

  return (
    <section>
      <h2>2. 학습 설정 설문 ({step}/3)</h2>

      {step === 1 && (
        <>
          <p style={{ color: "#555" }}>학습 범위를 선택하세요. (필수)</p>
          <div style={{ display: "grid", gap: "0.75rem", maxWidth: 480, marginTop: "1rem" }}>
            <label>
              시작
              <select
                value={rangeStart}
                onChange={(e) => setRangeStart(e.target.value)}
                style={{ display: "block", width: "100%", marginTop: 4 }}
              >
                {skeleton.toc.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.title} (p.{t.start_page}–{t.end_page})
                  </option>
                ))}
              </select>
            </label>
            <label>
              끝
              <select
                value={rangeEnd}
                onChange={(e) => setRangeEnd(e.target.value)}
                style={{ display: "block", width: "100%", marginTop: 4 }}
              >
                {skeleton.toc.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.title} (p.{t.start_page}–{t.end_page})
                  </option>
                ))}
              </select>
            </label>
          </div>
          <div style={{ marginTop: "1rem" }}>
            <Button onClick={() => setStep(2)} disabled={!rangeStart || !rangeEnd}>
              다음
            </Button>
          </div>
        </>
      )}

      {step === 2 && (
        <>
          <p style={{ color: "#555" }}>이미 알고 있다고 생각하는 선행지식을 선택하세요.</p>

          {prereqLoading && (
            <p style={{ color: "#666", fontSize: "0.9rem" }}>AI가 선행지식을 분석 중…</p>
          )}
          {prereqAnalysis?.summary && (
            <p style={{ color: "#336", fontSize: "0.9rem", marginTop: "0.5rem" }}>
              {prereqAnalysis.summary}
            </p>
          )}
          {prereqAnalysis && (
            <p style={{ fontSize: "0.8rem", color: "#666" }}>
              {prereqAnalysis.generation_mode === "llm" ? "✓ Solar 분석" : "⚠ 규칙 목록"}
              {prereqAnalysis.generation_note ? ` — ${prereqAnalysis.generation_note}` : ""}
            </p>
          )}
          {prereqError && <p style={{ color: "#a60", fontSize: "0.9rem" }}>{prereqError}</p>}

          <div style={{ marginTop: "1rem" }}>
            {aiSuggestions.length > 0 && (
              <>
                <strong>AI 추천 선행지식</strong>
                <ul style={{ listStyle: "none", padding: 0 }}>
                  {aiSuggestions.map((s) => (
                    <li key={`ai-${s.id}`} style={{ marginBottom: 6 }}>
                      <label>
                        <input
                          type="checkbox"
                          checked={knownBefore.has(s.id)}
                          onChange={() => toggleKnown(s.id)}
                        />{" "}
                        {s.label}
                        {s.recommended && (
                          <span style={{ color: "#a40", fontSize: "0.8rem" }}> (권장)</span>
                        )}
                        <span style={{ display: "block", color: "#888", fontSize: "0.8rem" }}>
                          {s.reason}
                        </span>
                      </label>
                    </li>
                  ))}
                </ul>
              </>
            )}

            {priorChapters.length > 0 && (
              <>
                <strong style={{ display: "block", marginTop: "1rem" }}>PDF 앞 단원</strong>
                <ul style={{ listStyle: "none", padding: 0 }}>
                  {priorChapters.map((t) => (
                    <li key={t.id}>
                      <label>
                        <input
                          type="checkbox"
                          checked={knownBefore.has(t.id)}
                          onChange={() => toggleKnown(t.id)}
                        />{" "}
                        {t.title}
                      </label>
                    </li>
                  ))}
                </ul>
              </>
            )}

            {skeleton.external_prerequisites.length > 0 && (
              <>
                <strong style={{ display: "block", marginTop: "1rem" }}>PDF 밖 선행지식</strong>
                <ul style={{ listStyle: "none", padding: 0 }}>
                  {skeleton.external_prerequisites.map((id) => (
                    <li key={id}>
                      <label>
                        <input
                          type="checkbox"
                          checked={knownBefore.has(id)}
                          onChange={() => toggleKnown(id)}
                        />{" "}
                        {PREREQUISITE_LABELS[id] ?? id}
                      </label>
                    </li>
                  ))}
                </ul>
              </>
            )}

            {aiOnlySuggestions.length === 0 &&
              priorChapters.length === 0 &&
              skeleton.external_prerequisites.length === 0 &&
              !prereqLoading && (
                <p style={{ color: "#888" }}>선택 가능한 선행지식 항목이 없습니다.</p>
              )}
          </div>

          <div style={{ marginTop: "1rem", display: "flex", gap: "0.5rem" }}>
            <Button onClick={() => setStep(1)}>이전</Button>
            <Button onClick={() => setStep(3)}>다음</Button>
          </div>
        </>
      )}

      {step === 3 && (
        <>
          <p style={{ color: "#555" }}>학습 목표를 선택하세요. (선택)</p>
          <div style={{ marginTop: "1rem", display: "flex", flexDirection: "column", gap: 8 }}>
            {(Object.keys(LEARNING_GOAL_LABELS) as LearningGoal[]).map((g) => (
              <label key={g}>
                <input
                  type="radio"
                  name="goal"
                  value={g}
                  checked={goal === g}
                  onChange={() => setGoal(g)}
                />{" "}
                {LEARNING_GOAL_LABELS[g]}
              </label>
            ))}
            <label>
              <input
                type="radio"
                name="goal"
                value=""
                checked={goal === ""}
                onChange={() => setGoal("")}
              />{" "}
              선택 안 함
            </label>
          </div>
          <div style={{ marginTop: "1rem", display: "flex", gap: "0.5rem" }}>
            <Button onClick={() => setStep(2)}>이전</Button>
            <Button disabled={isPending} onClick={handleFinalSubmit}>
              {isPending ? "AI 진단 문제 생성 중…" : "설문 완료 · 진단 시작"}
            </Button>
          </div>
        </>
      )}

      {error && <p style={{ color: "crimson", marginTop: "0.75rem" }}>{error}</p>}
    </section>
  );
}
