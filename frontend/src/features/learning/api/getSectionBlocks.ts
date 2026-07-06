// GET /api/sections/:id — 절의 검증된 봉투 배열(정답 스트립·variant 필터 적용된 서빙).
import { apiClient } from "@/shared/api/client";
import type { LearningBlock } from "@/features/learning/blocks/types";

export type SectionBlocks = {
  id: string;
  title: string;
  conceptId: string | null;
  variant: string;
  blocks: LearningBlock[];
};

export async function getSectionBlocks(sectionId: string): Promise<SectionBlocks> {
  const { data } = await apiClient.get<SectionBlocks>(
    `/api/sections/${sectionId}`,
  );
  return data;
}
