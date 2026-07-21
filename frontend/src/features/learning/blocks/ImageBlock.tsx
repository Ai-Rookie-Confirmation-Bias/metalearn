import { useState } from "react";
import { ImageBrokenIcon } from "@phosphor-icons/react";

import { apiBaseUrl } from "@/shared/api/client";
import { Prose } from "@/shared/ui/Prose";

import type { ImageBlockData } from "./types";

// ① 교재 그림 블록 — 읽기만, 추적 없음(onAnswer 없음).
// AI가 그린 게 아니라 원문에서 잘라온 그림(doc_figures) — 환각 0, 그림 자체가 근거.
// explanation(원문 근거 기반 안내)이 있으면 그림 아래에 표시 — "그림만 덩그러니" 방지.
export function ImageBlock({ data }: { data: ImageBlockData }) {
  const [failed, setFailed] = useState(false);
  const src = `${apiBaseUrl}/api/documents/figures/${data.figureId}`;

  return (
    <figure>
      {failed ? (
        <div className="flex items-center justify-center gap-2 rounded-xl border border-dashed border-border-primary bg-bg-secondary/50 py-10 text-text-tertiary">
          <ImageBrokenIcon className="text-2xl" />
          그림을 불러오지 못했어요
        </div>
      ) : (
        <img
          src={src}
          alt={data.caption ?? "교재 그림"}
          loading="lazy"
          onError={() => setFailed(true)}
          className="mx-auto max-h-[420px] max-w-full rounded-xl border border-border-primary bg-white object-contain"
        />
      )}
      <figcaption className="mt-2 flex items-center justify-between text-[0.82rem] text-text-tertiary">
        <span>{data.caption ?? "교재 원문 그림"}</span>
        {data.page != null && <span>교재 {data.page}쪽</span>}
      </figcaption>
      {data.explanation && (
        <div className="mt-3 rounded-xl border-l-4 border-[#6366f1] bg-[#6366f1]/[0.06] p-4">
          <span className="mb-1.5 block text-xs font-bold text-[#6366f1]">
            이 그림은
          </span>
          <Prose
            text={data.explanation}
            className="text-[0.92rem] leading-relaxed text-text-secondary"
          />
        </div>
      )}
    </figure>
  );
}
