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
    // 아래는 상류(parsing/materials) 소관이라 우리 응답엔 없음 → 잠정 파생값.
    difficultyEst: 0, // documents.difficulty_est
    // 진단 상태 프록시: 씨앗 조립(seed build) 전이면 섹션이 0개 → "진단 전"으로 간주.
    // TODO: 서버가 enrollments.diag_status를 내려주면 그 값으로 교체.
    diagStatus: c.totalSections > 0 ? "completed" : "not_started",
  }));
}
