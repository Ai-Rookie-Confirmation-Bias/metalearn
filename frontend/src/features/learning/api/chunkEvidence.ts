// GET /api/chunks/evidence — 근거 보기: 블록이 근거로 삼은 교재 원문 구절.
// blockId를 주면 청크 전체가 아니라 블록과 관련된 문단만 추려서 온다(범위 좁힘).
// "AI가 근거를 댈 뿐 아니라 그 원문을 즉석에서 보여준다" = 추적 가능한 AI.
import { apiClient } from "@/shared/api/client";

export type EvidencePassage = {
  text: string;
  page: number | null;
};
export type ChunkEvidence = {
  passages: EvidencePassage[];
  documentId: string | null;
  pageFrom: number | null;
  pageTo: number | null;
};

export async function getChunkEvidence(
  chunkIds: string[],
  blockId?: string,
): Promise<ChunkEvidence> {
  if (chunkIds.length === 0)
    return { passages: [], documentId: null, pageFrom: null, pageTo: null };
  const { data } = await apiClient.get<ChunkEvidence>("/api/chunks/evidence", {
    params: { ids: chunkIds.join(","), ...(blockId ? { blockId } : {}) },
  });
  return data;
}

export type PageContentItem = { page: number; text: string };

// 언급된 페이지의 교재 원문 전체(맥락 확장) — refined_elements 페이지 경계 기준.
export async function getPageContent(
  documentId: string,
  pageFrom: number,
  pageTo: number,
): Promise<PageContentItem[]> {
  const { data } = await apiClient.get<{ items: PageContentItem[] }>(
    "/api/documents/page-content",
    { params: { documentId, pageFrom, pageTo } },
  );
  return data.items;
}
