// POST /api/blocks/:id/supplement — 오답 맞춤 보충(재설명). 개입 사다리 ②(ISSUE-005).
// 채점(POST /attempts)이 nextAction=supplement를 주면 뒤따라 호출한다(reveal은 즉시,
// 재설명은 수 초 뒤 도착). 응답은 개인화 콘텐츠(학습자의 실제 오답 기반)라 비영속.
import { apiClient } from "@/shared/api/client";

export type SupplementResponse = {
  blockId: string;
  conceptId: string;
  diagnosis: string; // 무엇을 놓쳤/오해했는지(학습자에게 직접 말하는 문장)
  misconception: boolean; // 오개념 판정(다음 국소화의 신호로도 쓰임)
  title: string;
  body: string; // 오해를 겨냥한 재설명
  fallback: boolean; // LLM 실패 → 근거 인용 폴백 여부
};

export async function getSupplement(blockId: string): Promise<SupplementResponse> {
  const { data } = await apiClient.post<SupplementResponse>(
    `/api/blocks/${blockId}/supplement`,
  );
  return data;
}
