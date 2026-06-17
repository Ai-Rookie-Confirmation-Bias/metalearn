// [1단계] 순수 백엔드 호출 함수 (또는 runtime provider 경유)
import { generate } from "@/runtime/provider";
import { learningPrompts } from "@/features/learning/prompts";

export function requestGenerate(topic: string): Promise<string> {
  return generate({ topic, prompt: learningPrompts.generate(topic) });
}
