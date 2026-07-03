import { useMutation } from "@tanstack/react-query";
import { useState } from "react";

import {
  bootstrapFromDocument,
  fetchSeedSlice,
  generateCurriculum,
  submitDiagnostic,
  uploadDocument,
} from "@/features/seed/api/seedApi";
import { CurriculumView } from "@/features/seed/components/CurriculumView";
import { DiagnosticQuiz } from "@/features/seed/components/DiagnosticQuiz";
import { PdfUploadStep } from "@/features/seed/components/PdfUploadStep";
import type {
  AnswerItem,
  Curriculum,
  DiagnosticSession,
  SeedSlice,
} from "@/features/seed/types";

type FlowStep = "upload" | "diagnostic" | "curriculum";

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

export function SeedPage() {
  const [flowStep, setFlowStep] = useState<FlowStep>("upload");
  const [session, setSession] = useState<DiagnosticSession | null>(null);
  const [prerequisiteCount, setPrerequisiteCount] = useState(0);
  const [seedSlice, setSeedSlice] = useState<SeedSlice | null>(null);
  const [curriculum, setCurriculum] = useState<Curriculum | null>(null);
  const [flowError, setFlowError] = useState<string | null>(null);

  const uploadMutation = useMutation({
    mutationFn: async (file: File) => {
      const doc = await uploadDocument(file);
      const boot = await bootstrapFromDocument(doc.id);
      return { doc, boot };
    },
    onSuccess: ({ boot }) => {
      setFlowError(null);
      setSession(boot.diagnostic);
      setPrerequisiteCount(boot.prerequisite_count);
      setFlowStep("diagnostic");
    },
    onError: (err) => setFlowError(getErrorMessage(err)),
  });

  const submitMutation = useMutation({
    mutationFn: async (answers: AnswerItem[]) => {
      if (!session) throw new Error("진단 세션이 없습니다.");
      const result = await submitDiagnostic(session.id, answers);
      const slice = await fetchSeedSlice(result.profile_id);
      const curriculumData = await generateCurriculum(result.profile_id);
      return { result, slice, curriculum: curriculumData };
    },
    onSuccess: ({ result, slice, curriculum: curriculumData }) => {
      setFlowError(null);
      setSession((prev) => (prev ? { ...prev, status: result.status } : prev));
      setSeedSlice(slice);
      setCurriculum(curriculumData);
      setFlowStep("curriculum");
    },
    onError: (err) => setFlowError(getErrorMessage(err)),
  });

  const reset = () => {
    setFlowStep("upload");
    setSession(null);
    setPrerequisiteCount(0);
    setSeedSlice(null);
    setCurriculum(null);
    setFlowError(null);
  };

  return (
    <div>
      <h1>Seed — PDF · 진단 · 커리큘럼</h1>
      <p style={{ color: "#666", marginBottom: "1.5rem" }}>
        PDF 업로드 → Solar가 사전지식 탐색 · 진단 → 개인 맞춤 학습 로드맵
      </p>

      <nav style={{ marginBottom: "1.5rem", fontSize: "0.9rem", color: "#888" }}>
        {(["upload", "diagnostic", "curriculum"] as FlowStep[]).map((s, i) => (
          <span key={s}>
            {i > 0 && " → "}
            <span style={{ fontWeight: flowStep === s ? 700 : 400, color: flowStep === s ? "#111" : "#888" }}>
              {s === "upload" && "업로드"}
              {s === "diagnostic" && "진단"}
              {s === "curriculum" && "커리큘럼"}
            </span>
          </span>
        ))}
      </nav>

      {flowStep === "upload" && (
        <PdfUploadStep
          onUpload={(file) => uploadMutation.mutate(file)}
          isPending={uploadMutation.isPending}
          error={flowError}
        />
      )}

      {flowStep === "diagnostic" && session && (
        <DiagnosticQuiz
          questions={session.questions}
          prerequisiteCount={prerequisiteCount}
          onSubmit={(answers) => submitMutation.mutate(answers)}
          isPending={submitMutation.isPending}
          error={flowError}
          generationMode={session.generation_mode}
          generationNote={session.generation_note}
        />
      )}

      {flowStep === "curriculum" &&
        session &&
        seedSlice &&
        curriculum &&
        submitMutation.data && (
          <CurriculumView
            result={submitMutation.data.result}
            slice={seedSlice}
            curriculum={curriculum}
            onReset={reset}
          />
        )}
    </div>
  );
}
