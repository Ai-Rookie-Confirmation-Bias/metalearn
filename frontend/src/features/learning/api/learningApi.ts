import { apiClient, llmApiClient } from "@/shared/api/client";
import type {
  CompleteSessionResponse,
  HintResponse,
  RespondResponse,
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

export async function completeSession(sessionId: string): Promise<CompleteSessionResponse> {
  const { data } = await apiClient.post<CompleteSessionResponse>(
    `/api/learning/sessions/${sessionId}/complete`,
  );
  return data;
}
