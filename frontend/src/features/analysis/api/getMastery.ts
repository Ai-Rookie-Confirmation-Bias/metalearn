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
  // 커리큘럼 절의 대표 개념이면 그 절 id — 지식 지도 노드 필터 + 클릭→학습 이동
  sectionId: string | null;
};
// 개념 간 관계(지식 지도 엣지). from=학습대상 → to=선행 (parsing 규약).
export type ConceptEdgeItem = {
  fromConceptId: string;
  toConceptId: string;
  kind: "prerequisite" | "contains" | string;
};
export type MasteryResponse = {
  courseId: string;
  mastered: number;
  learning: number;
  todo: number;
  locked: number;
  concepts: ConceptMasteryItem[];
  edges: ConceptEdgeItem[];
};

export async function getMastery(courseId: string): Promise<MasteryResponse> {
  const { data } = await apiClient.get<MasteryResponse>(
    `/api/courses/${courseId}/mastery`,
  );
  return data;
}
