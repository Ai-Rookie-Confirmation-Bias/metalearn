import type { AnalogyBlockData } from "./types";

// ① 비유 블록 — 읽기만, 추적 없음(tracked=false, onAnswer 없음).
// 서버가 label("비유")을 강제해(schemas.AnalogyData) 사실 설명과 혼동되지 않게 한다
// → 라벨 배지 + 인용문(콜아웃) 스타일로 "설명이 아니라 발판"임을 시각적으로 구분.
export function AnalogyBlock({ data }: { data: AnalogyBlockData }) {
  return (
    <div className="rounded-xl border-l-4 border-[#8b5cf6] bg-[#8b5cf6]/5 p-5">
      <span className="mb-2.5 inline-block rounded-full bg-[#8b5cf6]/10 px-2.5 py-1 text-xs font-bold text-[#8b5cf6]">
        {data.label}
      </span>
      <blockquote className="text-[1.05rem] italic leading-[1.7] text-text-secondary">
        {data.text}
      </blockquote>
    </div>
  );
}
