import { Prose } from "@/shared/ui/Prose";

import type { ConceptBlockData } from "./types";

// ① 설명 블록 — 읽기만, 추적 없음(onAnswer 없음).
// 본문은 Prose로: 줄바꿈을 문단으로 살리고 **강조**·`코드`를 렌더(텍스트 벽 해소).
export function ConceptBlock({ data }: { data: ConceptBlockData }) {
  return (
    <Prose
      text={data.body}
      className="text-[1.05rem] leading-[1.8] text-text-secondary"
    />
  );
}
