// [1단계] 백엔드 호출 함수. 진단은 클라우드 LLM 채점 기반이라 apiClient 직접 사용.
import { apiClient } from "@/shared/api/client";
import type { AnswerResult, SessionState } from "@/features/diagnostic/types";

// 문항 생성/채점(LLM)이 끼어 있어 길 수 있음. answer는 채점+다음문항 생성이 연달아
// 일어날 수 있어 넉넉히(백엔드 생성 타임아웃 120s × 2 여유).
const _TIMEOUT = 240_000;

export async function startDiagnostic(courseId: number): Promise<SessionState> {
  const { data } = await apiClient.post<SessionState>(
    "/api/diagnostic/start",
    { course_id: courseId },
    { timeout: _TIMEOUT },
  );
  return data;
}

export async function fetchState(sessionId: number): Promise<SessionState> {
  const { data } = await apiClient.get<SessionState>(`/api/diagnostic/${sessionId}`, {
    timeout: _TIMEOUT,
  });
  return data;
}

export interface AnswerInput {
  selected_index?: number;
  answer_text?: string;
}

export async function submitAnswer(
  sessionId: number,
  questionId: number,
  input: AnswerInput,
): Promise<AnswerResult> {
  const { data } = await apiClient.post<AnswerResult>(
    `/api/diagnostic/${sessionId}/questions/${questionId}/answer`,
    input,
    { timeout: _TIMEOUT },
  );
  return data;
}
