// 🧠 [하이브리드 AI 트래픽 컨트롤러] ★ 분기 지점
// 온라인 → 서버(Solar) 호출 / 오프라인 → 로컬 EXAONE 엔진.
import { apiClient } from "@/shared/api/client";
import { isOnline } from "@/shared/utils/network";
import { runLocalEngine } from "@/runtime/engine";

export interface GenerateParams {
  topic: string;
  prompt: string; // 로컬 엔진용 (features/*/prompts.ts에서 구성)
}

export async function generate({ topic, prompt }: GenerateParams): Promise<string> {
  if (isOnline()) {
    // MVP: 온라인 경로만 실제 동작
    const { data } = await apiClient.post<{ content: string }>("/api/learning/generate", {
      topic,
    });
    return data.content;
  }
  // Phase 2: 오프라인 로컬 엔진
  return runLocalEngine(prompt);
}
