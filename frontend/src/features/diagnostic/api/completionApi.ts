// 진단 완료 후처리 API — 씨앗(커리큘럼 트리) 조립 + 수준 배치(placement).
// 계약: POST /api/seed/{course_id}/build → POST /api/courses/{course_id}/placement.
// 서버가 진실(마스터리·트리) — 클라는 순서대로 호출만 하고 결과를 신뢰한다.
import { apiClient } from "@/shared/api/client";

// 씨앗 조립은 슬러그 생성 등 LLM 호출이 끼어 길어질 수 있음.
const _TIMEOUT = 240_000;

/** 커리큘럼 트리 + enrollment 확정. purpose는 수업 생성 3스텝의 학습 목표. */
export async function buildSeed(courseId: string, purpose?: string): Promise<unknown> {
  const { data } = await apiClient.post(
    `/api/seed/${courseId}/build`,
    null,
    { params: purpose ? { purpose } : undefined, timeout: _TIMEOUT },
  );
  return data;
}

/** 진단 결과(floor/ceiling) 기준 concept_mastery 시딩 — 학습 시작 지점 확정. */
export async function initPlacement(courseId: string): Promise<unknown> {
  const { data } = await apiClient.post(
    `/api/courses/${courseId}/placement`,
    null,
    { timeout: _TIMEOUT },
  );
  return data;
}
