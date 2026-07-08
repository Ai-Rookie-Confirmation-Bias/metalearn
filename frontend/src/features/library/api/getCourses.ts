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
  diagStatus: string; // enrollments.diag_status (ISSUE-018)
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
    // 진단 상태(ISSUE-018): 서버 enrollments.diag_status를 그대로 사용.
    // (예전 totalSections>0 프록시는 ingest 후 온보딩 전에도 완료로 오판했음)
    diagStatus: (c.diagStatus ?? "not_started") as CourseSummary["diagStatus"],
  }));
}
