import type { ConceptBlockData } from "./types";

// ① 설명 블록 — 읽기만, 추적 없음(onAnswer 없음)
export function ConceptBlock({ data }: { data: ConceptBlockData }) {
  // body 안의 **강조** 마크만 <strong>으로 (mock 수준의 최소 파서)
  const parts = data.body.split(/\*\*(.+?)\*\*/g);
  return (
    <div className="text-[1.05rem] leading-[1.7] text-text-secondary">
      {parts.map((p, i) =>
        i % 2 === 1 ? (
          <strong key={i} className="font-bold text-text-primary">
            {p}
          </strong>
        ) : (
          p
        ),
      )}
    </div>
  );
}
