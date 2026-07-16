// POST /api/attempts — 서버 채점(라운드트립). 클라 correct는 안 보낸다(서버가 판정).
// 응답: 채점(correct/score/reveal) + 살아있는 커리큘럼 신호(nextAction/cause/prerequisite/resume).
// 서버가 안 닿으면(Network Error) 로컬 엔진 어댑터로 폴백 — 클라우드+로컬 이중구조.
import { isAxiosError } from "axios";

import { apiClient } from "@/shared/api/client";
import { submitAttemptOffline } from "@/shared/api/offline";
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
  // 로컬 sLLM(EXAONE 1.2B) 채점 여부 — UI가 "오프라인 채점" 배지를 띄운다
  offline?: boolean;
};

export async function submitAttempt(e: AnswerEvent): Promise<AttemptResponse> {
  const body = {
    blockId: e.blockId,
    conceptId: e.conceptId,
    kind: e.kind ?? "learn",
    userInput: e.userInput,
  };
  try {
    const { data } = await apiClient.post<AttemptResponse>("/api/attempts", body);
    return data;
  } catch (error) {
    // 서버 응답이 있는 실패(4xx/5xx)는 그대로 던진다 — 폴백 대상은 '연결 자체 불가'만
    if (isAxiosError(error) && !error.response) {
      return (await submitAttemptOffline(body)) as AttemptResponse;
    }
    throw error;
  }
}
