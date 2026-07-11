// GET /api/courses/:id — 챕터/절 트리(커리큘럼 패널·네비용). 블록은 절 선택 시 별도 로드.
import { apiClient } from "@/shared/api/client";

export type TreeSection = {
  id: string;
  title: string;
  orderIndex: number;
  conceptId: string | null;
  progressStatus: string; // not_started | in_progress | completed
  variantServed: string | null;
  masteryStatus: string | null;
  strength: number | null;
  locked: boolean; // 서버 계산(순차 잠금) — 프론트는 미러만
};
export type TreeChapter = {
  id: string;
  title: string;
  orderIndex: number;
  origin: string; // book | prereq
  genStatus: string; // pending | generating | ready | failed
  // 이유 라벨(변화 가시성): prereq 챕터가 왜 생겼는지 서버가 문장으로 내려줌
  reason?: string | null;
  sections: TreeSection[];
};
export type CourseTree = {
  courseId: string;
  title: string;
  chapters: TreeChapter[];
};

export async function getCourseTree(courseId: string): Promise<CourseTree> {
  const { data } = await apiClient.get<CourseTree>(`/api/courses/${courseId}`);
  return data;
}
