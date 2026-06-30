// [1단계] 백엔드 호출. JIT 커리큘럼은 클라우드 LLM 생성이라 apiClient 직접 사용.
import { apiClient } from "@/shared/api/client";
import type { CurriculumResponse } from "@/features/learning/curriculumTypes";

export interface CurriculumArgs {
  conceptId: number;
  sessionId?: number;
  forceRegenerate?: boolean;
}

export async function requestCurriculum({
  conceptId,
  sessionId,
  forceRegenerate,
}: CurriculumArgs): Promise<CurriculumResponse> {
  const { data } = await apiClient.post<CurriculumResponse>(
    "/api/learning/curriculum",
    {
      concept_id: conceptId,
      session_id: sessionId ?? null,
      force_regenerate: forceRegenerate ?? false,
    },
    { timeout: 180_000 },
  );
  return data;
}
