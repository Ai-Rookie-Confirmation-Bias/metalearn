// POST /api/tutor/chat — 현재 절 근거로 접지된 AI 튜터 Q&A.
// 정답 비유출(소크라틱)은 서버 프롬프트가 강제한다 — 퀴즈 정답을 물으면 힌트로 유도.
// 대화는 서버 무저장: 프론트가 history로 왕복(개인화 콘텐츠 비영속 원칙, supplement와 동일).
import { llmApiClient } from "@/shared/api/client";

export type TutorChatTurn = { role: "user" | "tutor"; text: string };

export type TutorChatResponse = {
  sectionId: string;
  reply: string;
};

export async function postTutorChat(params: {
  sectionId: string;
  message: string;
  history: TutorChatTurn[];
}): Promise<TutorChatResponse> {
  const { data } = await llmApiClient.post<TutorChatResponse>("/api/tutor/chat", {
    sectionId: params.sectionId,
    message: params.message,
    history: params.history.slice(-12),
  });
  return data;
}
