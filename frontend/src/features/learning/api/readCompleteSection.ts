// POST /api/sections/:id/read-complete — tracked 0개 절(예: analogy만)의 열람 완료 처리.
// 채점 대상 블록이 있으면 서버가 409로 거절한다(판단은 서버). 완료 시 커서 복귀도 pop.
import { apiClient } from "@/shared/api/client";

export type ReadCompleteResponse = {
  sectionId: string;
  status: string; // completed
  resumeSectionId?: string | null; // 선행 완료로 복귀할 원래 절(없으면 null)
};

export async function readCompleteSection(sectionId: string): Promise<ReadCompleteResponse> {
  const { data } = await apiClient.post<ReadCompleteResponse>(
    `/api/sections/${sectionId}/read-complete`,
  );
  return data;
}
