// 배치고사(placement, ISSUE-015) 백엔드 호출. 구형 진단(diagnosticApi)을 대체.
// 문항 1개씩 서빙 — start로 첫 문항, answer로 다음 문항(또는 done+시드).
import { apiClient } from "@/shared/api/client";
import type { PlacementState } from "@/features/diagnostic/types";

// 문항 생성·검증(LLM)이 끼어 있어 넉넉히(백엔드 생성 타임아웃 대비).
const _TIMEOUT = 240_000;

export async function startPlacement(courseId: string): Promise<PlacementState> {
  const { data } = await apiClient.post<PlacementState>(
    "/api/diagnostic/placement/start",
    { course_id: courseId },
    { timeout: _TIMEOUT },
  );
  return data;
}

export interface PlacementAnswerInput {
  selected_index?: number;
  answer_text?: string;
}

export async function answerPlacement(
  sessionId: string,
  questionId: string,
  input: PlacementAnswerInput,
): Promise<PlacementState> {
  const { data } = await apiClient.post<PlacementState>(
    `/api/diagnostic/placement/${sessionId}/questions/${questionId}/answer`,
    input,
    { timeout: _TIMEOUT },
  );
  return data;
}
