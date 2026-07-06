// GET /api/courses/:id/mastery — 개념별 숙련도 + 상태별 요약(메타인지 분석).
import { apiClient } from "@/shared/api/client";

export type ConceptMasteryItem = {
  conceptId: string;
  key: string | null;
  name: string;
  depthLevel: number | null;
  status: "locked" | "todo" | "learning" | "mastered";
  strength: number;
  explanationScore: number;
  confidence: string | null;
  nextDueAt: string | null;
};
export type MasteryResponse = {
  courseId: string;
  mastered: number;
  learning: number;
  todo: number;
  locked: number;
  concepts: ConceptMasteryItem[];
};

export async function getMastery(courseId: string): Promise<MasteryResponse> {
  const { data } = await apiClient.get<MasteryResponse>(
    `/api/courses/${courseId}/mastery`,
  );
  return data;
}
