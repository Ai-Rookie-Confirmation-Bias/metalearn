import { useMutation } from "@tanstack/react-query";
import { useState } from "react";

import {
  createProfile,
  fetchSeedSlice,
  fetchSkeleton,
  generateCurriculum,
  startDiagnostic,
  submitDiagnostic,
  uploadDocument,
} from "@/features/seed/api/seedApi";
import { CurriculumView } from "@/features/seed/components/CurriculumView";
import { DiagnosticQuiz } from "@/features/seed/components/DiagnosticQuiz";
import { PdfUploadStep } from "@/features/seed/components/PdfUploadStep";
import { SurveyWizard } from "@/features/seed/components/SurveyWizard";
import type {
  Curriculum,
  DiagnosticSession,
  DocumentResponse,
  DocumentSkeleton,
  LearningGoal,
  SeedSlice,
} from "@/features/seed/types";

type FlowStep = "upload" | "survey" | "diagnostic" | "curriculum";

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
  const [document, setDocument] = useState<DocumentResponse | null>(null);
  const [skeleton, setSkeleton] = useState<DocumentSkeleton | null>(null);
  const [session, setSession] = useState<DiagnosticSession | null>(null);
  const [seedSlice, setSeedSlice] = useState<SeedSlice | null>(null);
  const [curriculum, setCurriculum] = useState<Curriculum | null>(null);
  const [flowError, setFlowError] = useState<string | null>(null);

  const uploadMutation = useMutation({
    mutationFn: uploadDocument,
    onSuccess: async (doc) => {
      setFlowError(null);
      setDocument(doc);
      const sk = await fetchSkeleton(doc.id);
      setSkeleton(sk);
      setFlowStep("survey");
    },
    onError: (err) => setFlowError(getErrorMessage(err)),
  });

  const surveyMutation = useMutation({
    mutationFn: async (payload: {
      learning_range: { start: string; end: string };
      known_before: string[];
      learning_goal: LearningGoal | null;
    }) => {
      if (!document) throw new Error("문서가 없습니다.");
      const profile = await createProfile({
        document_id: document.id,
        ...payload,
      });
      return startDiagnostic(profile.id);
    },
    onSuccess: (diagSession) => {
      setFlowError(null);
      setSession(diagSession);
      setFlowStep("diagnostic");
    },
    onError: (err) => setFlowError(getErrorMessage(err)),
  });

  const submitMutation = useMutation({
    mutationFn: async (choices: Record<string, number>) => {
      if (!session) throw new Error("진단 세션이 없습니다.");
      const answers = Object.entries(choices).map(([question_id, choice_index]) => ({
        question_id,
        choice_index,
      }));
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
    setDocument(null);
    setSkeleton(null);
    setSession(null);
    setSeedSlice(null);
    setCurriculum(null);
    setFlowError(null);
  };

  return (
    <div>
      <h1>Seed — PDF · 설문 · 진단 · 커리큘럼</h1>
      <p style={{ color: "#666", marginBottom: "1.5rem" }}>
        PDF 업로드 → 3단계 설문 → 진단 → 개인 맞춤 학습 로드맵
      </p>

      <nav style={{ marginBottom: "1.5rem", fontSize: "0.9rem", color: "#888" }}>
        {(["upload", "survey", "diagnostic", "curriculum"] as FlowStep[]).map((s, i) => (
          <span key={s}>
            {i > 0 && " → "}
            <span style={{ fontWeight: flowStep === s ? 700 : 400, color: flowStep === s ? "#111" : "#888" }}>
              {s === "upload" && "업로드"}
              {s === "survey" && "설문"}
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

      {flowStep === "survey" && skeleton && (
        <SurveyWizard
          skeleton={skeleton}
          onSubmit={(payload) => surveyMutation.mutate(payload)}
          isPending={surveyMutation.isPending}
          error={flowError}
        />
      )}

      {flowStep === "diagnostic" && session && (
        <DiagnosticQuiz
          questions={session.questions}
          onSubmit={(choices) => submitMutation.mutate(choices)}
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
