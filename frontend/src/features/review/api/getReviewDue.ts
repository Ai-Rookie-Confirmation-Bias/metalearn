// GET /api/review/due — 복습 도래 개념(+ 다시 답할 블록). courseId 없으면 전체.
import { apiClient } from "@/shared/api/client";
import type { LearningBlock } from "@/features/learning/blocks/types";

export type ReviewDueItem = {
  conceptId: string;
  conceptName: string;
  sectionId: string | null;
  nextDueAt: string | null;
  block: LearningBlock | null;
};
export type ReviewDueResponse = { dueCount: number; items: ReviewDueItem[] };

export async function getReviewDue(courseId?: string): Promise<ReviewDueResponse> {
  const { data } = await apiClient.get<ReviewDueResponse>("/api/review/due", {
    params: courseId ? { courseId } : {},
  });
  return data;
}
