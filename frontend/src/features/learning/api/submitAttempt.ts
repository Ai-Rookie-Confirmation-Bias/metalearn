// POST /api/attempts — 서버 채점(라운드트립). 클라 correct는 안 보낸다(서버가 판정).
// 응답: 채점(correct/score/reveal) + 살아있는 커리큘럼 신호(nextAction/cause/prerequisite/resume).
import { apiClient } from "@/shared/api/client";
import type { AnswerEvent, AttemptResult } from "@/features/learning/blocks/types";

export type AttemptResponse = AttemptResult & {
  nextAction?: { action: string; reason: string } | null;
  cause?: { type: string; reason: string; blameConceptId?: string | null } | null;
  prerequisite?: {
    conceptId: string;
    chapterId: string;
    sectionId: string;
    title: string;
    genStatus: string;
    created: boolean;
  } | null;
  resumeSectionId?: string | null;
};

export async function submitAttempt(e: AnswerEvent): Promise<AttemptResponse> {
  const { data } = await apiClient.post<AttemptResponse>("/api/attempts", {
    blockId: e.blockId,
    conceptId: e.conceptId,
    kind: e.kind ?? "learn",
    userInput: e.userInput,
  });
  return data;
}
