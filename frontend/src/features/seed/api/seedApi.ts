import { apiClient, llmApiClient } from "@/shared/api/client";
import type {
  AnswerItem,
  BootstrapResponse,
  Curriculum,
  DiagnosticResult,
  DiagnosticSession,
  DocumentResponse,
  DocumentSkeleton,
  LearningRange,
  PrerequisiteAnalysis,
  SeedProfileResponse,
  SeedSlice,
  SurveyRequest,
} from "@/features/seed/types";

export async function uploadDocument(file: File): Promise<DocumentResponse> {
  const form = new FormData();
  form.append("file", file);
  const { data } = await llmApiClient.post<DocumentResponse>("/api/materials/documents", form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

export async function fetchSkeleton(documentId: string): Promise<DocumentSkeleton> {
  const { data } = await apiClient.get<DocumentSkeleton>(
    `/api/materials/documents/${documentId}/skeleton`,
  );
  return data;
}

export async function bootstrapFromDocument(documentId: string): Promise<BootstrapResponse> {
  const { data } = await llmApiClient.post<BootstrapResponse>("/api/seed/bootstrap", {
    document_id: documentId,
  });
  return data;
}

export async function createProfile(body: SurveyRequest): Promise<SeedProfileResponse> {
  const { data } = await apiClient.post<SeedProfileResponse>("/api/seed/profiles", body);
  return data;
}

export async function startDiagnostic(profileId: string): Promise<DiagnosticSession> {
  const { data } = await llmApiClient.post<DiagnosticSession>(
    `/api/seed/profiles/${profileId}/diagnostics`,
  );
  return data;
}

export async function submitDiagnostic(
  sessionId: string,
  answers: AnswerItem[],
): Promise<DiagnosticResult> {
  const { data } = await llmApiClient.post<DiagnosticResult>(
    `/api/seed/diagnostics/${sessionId}/submit`,
    { answers },
  );
  return data;
}

export async function analyzePrerequisites(body: {
  document_id: string;
  learning_range: LearningRange;
}): Promise<PrerequisiteAnalysis> {
  const { data } = await llmApiClient.post<PrerequisiteAnalysis>(
    "/api/seed/prerequisites/analyze",
    body,
  );
  return data;
}

export async function fetchSeedSlice(profileId: string): Promise<SeedSlice> {
  const { data } = await apiClient.get<SeedSlice>(`/api/seed/profiles/${profileId}/slice`);
  return data;
}

export async function generateCurriculum(profileId: string): Promise<Curriculum> {
  const { data } = await llmApiClient.post<Curriculum>(
    `/api/seed/profiles/${profileId}/curriculum`,
  );
  return data;
}

export async function fetchCurriculum(profileId: string): Promise<Curriculum> {
  const { data } = await apiClient.get<Curriculum>(
    `/api/seed/profiles/${profileId}/curriculum`,
  );
  return data;
}
