// 실제 API 응답 모양 그대로의 읽기 DTO + 목업.
// 백엔드 붙이면 이 파일의 값 부분만 fetch로 교체하면 됨(타입·화면 그대로).

// GET /me/stats — 대시보드 통계(성취 지표는 나중에 메타인지 분석에서 확장)
export type MeStats = {
  streakDays: number; // 연속 학습일 — attempts.created_at 파생
};

// GET /courses 항목 — courses + documents + enrollments + section_progress 집계 조인 DTO
export type CourseSummary = {
  id: string; // courses.id
  title: string; // courses.title
  category: string | null; // courses.category
  difficultyEst: number; // documents.difficulty_est (1~10)
  diagStatus: "not_started" | "in_progress" | "completed"; // enrollments.diag_status
  sectionsTotal: number; // section 수
  sectionsCompleted: number; // section_progress(status=completed) 집계
  nextSectionTitle?: string; // 다음 학습할 절(첫 not_started section) — 이어서 배너용 힌트
  lastActivityAt: string | null; // 마지막 학습 시각 = MAX(attempts.created_at). 계산값(컬럼 아님), 활동 없으면 null
};

export const meStats: MeStats = {
  streakDays: 14,
};

export const courses: CourseSummary[] = [
  {
    id: "crs_dl",
    title: "딥러닝 에센셜: 기초부터 실전까지",
    category: "AI & Machine Learning",
    difficultyEst: 5,
    diagStatus: "completed",
    sectionsTotal: 20,
    sectionsCompleted: 9, // 45%
    nextSectionTitle: "역전파(Backpropagation)의 원리",
    lastActivityAt: "2026-07-02T20:10:00Z", // 가장 최근 → 배너 대상
  },
  {
    id: "crs_algo",
    title: "알고리즘적 사고와 문제해결력",
    category: "Computer Science",
    difficultyEst: 3,
    diagStatus: "completed",
    sectionsTotal: 15,
    sectionsCompleted: 12, // 80%
    nextSectionTitle: "정렬 알고리즘 비교",
    lastActivityAt: "2026-06-30T09:30:00Z", // 딥러닝보다 예전
  },
  {
    id: "crs_quantum",
    title: "양자 컴퓨팅 입문",
    category: "Emerging Tech",
    difficultyEst: 9,
    diagStatus: "not_started", // 아직 진단 전 → 진행바 대신 "진단 시작"
    sectionsTotal: 25,
    sectionsCompleted: 0,
    lastActivityAt: null, // 진단 전, 활동 없음
  },
];
