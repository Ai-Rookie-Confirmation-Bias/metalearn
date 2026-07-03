import { apiClient, llmApiClient } from "@/shared/api/client";
import type {
  BlockAnswerRequest,
  BlockAnswerResponse,
  BlockResponse,
  CompleteSessionResponse,
  HintResponse,
  LearnerModelResponse,
  RespondResponse,
  StartPrerequisiteResponse,
  StartSessionResponse,
} from "@/features/learning/types";
import type { CurriculumUnit } from "@/features/seed/types";

export async function startSession(
  profileId: string,
  unitOrder: CurriculumUnit["order"],
): Promise<StartSessionResponse> {
  const { data } = await llmApiClient.post<StartSessionResponse>("/api/learning/sessions", {
    profile_id: profileId,
    unit_order: unitOrder,
  });
  return data;
}

export async function submitResponse(
  sessionId: string,
  userResponse: string,
): Promise<RespondResponse> {
  const { data } = await llmApiClient.post<RespondResponse>(
    `/api/learning/sessions/${sessionId}/respond`,
    { user_response: userResponse },
  );
  return data;
}

export async function getHint(sessionId: string): Promise<HintResponse> {
  const { data } = await llmApiClient.get<HintResponse>(
    `/api/learning/sessions/${sessionId}/hint`,
  );
  return data;
}

export async function startPrerequisiteSession(
  sessionId: string,
): Promise<StartPrerequisiteResponse> {
  const { data } = await llmApiClient.post<StartPrerequisiteResponse>(
    `/api/learning/sessions/${sessionId}/prerequisite`,
  );
  return data;
}

export async function completeSession(sessionId: string): Promise<CompleteSessionResponse> {
  const { data } = await apiClient.post<CompleteSessionResponse>(
    `/api/learning/sessions/${sessionId}/complete`,
  );
  return data;
}

// ── 적응형 학습 블록 API ──────────────────────────────────────────────────────

export async function getNextBlock(profileId: string): Promise<BlockResponse> {
  const { data } = await llmApiClient.get<BlockResponse>(
    `/api/learning/profiles/${profileId}/next`,
  );
  return data;
}

export async function submitBlockAnswer(
  req: BlockAnswerRequest,
): Promise<BlockAnswerResponse> {
  const { data } = await llmApiClient.post<BlockAnswerResponse>(
    "/api/learning/blocks/answer",
    req,
  );
  return data;
}

export async function getLearnerModel(profileId: string): Promise<LearnerModelResponse> {
  const { data } = await apiClient.get<LearnerModelResponse>(
    `/api/learning/profiles/${profileId}/learner-model`,
  );
  return data;
}
