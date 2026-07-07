// [1단계] GET /api/courses — 책장 목록. 우리 백엔드 응답(CourseListItem)을
// 화면 DTO(CourseSummary)로 매핑한다. 백엔드 계약: curriculum/schemas.CourseListResponse.
import { apiClient } from "@/shared/api/client";
import type { CourseSummary } from "@/pages/library/mock";

type CourseListItemDTO = {
  courseId: string;
  title: string;
  category: string | null;
  conceptCount: number;
  totalSections: number;
  completedSections: number;
  progress: number;
  lastActivityAt: string | null;
};

export async function getCourses(): Promise<CourseSummary[]> {
  const { data } = await apiClient.get<{ courses: CourseListItemDTO[] }>(
    "/api/courses",
  );
  return data.courses.map((c) => ({
    id: c.courseId,
    title: c.title,
    category: c.category,
    sectionsTotal: c.totalSections,
    sectionsCompleted: c.completedSections,
    lastActivityAt: c.lastActivityAt,
    // 아래는 상류(parsing/materials) 소관이라 우리 응답엔 없음 → 잠정 기본값.
    difficultyEst: 0, // documents.difficulty_est
    diagStatus: "completed", // enrollments.diag_status (진단은 parsing)
  }));
}
