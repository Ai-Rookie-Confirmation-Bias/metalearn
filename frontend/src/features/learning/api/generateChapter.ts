// POST /api/chapters/:id/generate — JIT 생성 트리거(멱등, 백그라운드). 반환: 트리거 후 상태.
import { apiClient } from "@/shared/api/client";

export type GenerateResponse = { chapterId: string; genStatus: string };

export async function generateChapter(
  chapterId: string,
): Promise<GenerateResponse> {
  const { data } = await apiClient.post<GenerateResponse>(
    `/api/chapters/${chapterId}/generate`,
  );
  return data;
}
