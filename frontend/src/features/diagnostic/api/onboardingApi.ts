// 온보딩 진단(진단 재설계) — 성향 프로파일링 + 기반지식 체크.
// 배치고사(placement)를 대체하는 실사용 경로.
import { apiClient } from "@/shared/api/client";
import type { OnboardingState } from "@/features/diagnostic/types";

const _TIMEOUT = 240_000;

export async function startOnboarding(
  courseId: string,
  purpose?: string | null,
): Promise<OnboardingState> {
  const { data } = await apiClient.post<OnboardingState>(
    "/api/diagnostic/onboarding/start",
    { course_id: courseId, purpose: purpose ?? null },
    { timeout: _TIMEOUT },
  );
  return data;
}

export interface OnboardingAnswerInput {
  choice_index?: number;
  question_id?: string;
  selected_index?: number;
  answer_text?: string;
}

export async function answerOnboarding(
  sessionId: string,
  input: OnboardingAnswerInput,
): Promise<OnboardingState> {
  const { data } = await apiClient.post<OnboardingState>(
    `/api/diagnostic/onboarding/${sessionId}/answer`,
    input,
    { timeout: _TIMEOUT },
  );
  return data;
}
