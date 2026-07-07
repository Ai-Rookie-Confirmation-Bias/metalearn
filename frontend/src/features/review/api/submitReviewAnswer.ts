// POST /api/review/answer — 복습 응답(kind=review). 서버 채점 + SM-2 재스케줄.
// 응답은 attempt와 동일 모양(라운드트립 재사용).
import { apiClient } from "@/shared/api/client";
import type { AnswerEvent } from "@/features/learning/blocks/types";
import type { AttemptResponse } from "@/features/learning/api/submitAttempt";

export async function submitReviewAnswer(e: AnswerEvent): Promise<AttemptResponse> {
  const { data } = await apiClient.post<AttemptResponse>("/api/review/answer", {
    blockId: e.blockId,
    conceptId: e.conceptId,
    kind: "review",
    userInput: e.userInput,
  });
  return data;
}
