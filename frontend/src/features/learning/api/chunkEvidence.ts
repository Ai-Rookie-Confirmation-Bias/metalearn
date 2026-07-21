// GET /api/chunks/evidence — 근거 보기: 배지가 가리키는 청크의 교재 원문.
// "AI가 근거를 댈 뿐 아니라 그 원문을 즉석에서 보여준다" = 추적 가능한 AI.
import { apiClient } from "@/shared/api/client";

export type ChunkEvidence = {
  id: string;
  content: string;
  pageFrom: number | null;
  pageTo: number | null;
  heading: string | null;
};

export async function getChunkEvidence(chunkIds: string[]): Promise<ChunkEvidence[]> {
  if (chunkIds.length === 0) return [];
  const { data } = await apiClient.get<{ chunks: ChunkEvidence[] }>(
    "/api/chunks/evidence",
    { params: { ids: chunkIds.join(",") } },
  );
  return data.chunks;
}
