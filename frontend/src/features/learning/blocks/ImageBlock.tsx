import { useState } from "react";
import { ImageBrokenIcon, SparkleIcon } from "@phosphor-icons/react";

import { apiBaseUrl } from "@/shared/api/client";

import type { ImageBlockData } from "./types";

// ① 교재 그림 블록 — 읽기만, 추적 없음(onAnswer 없음).
// 그림은 원문에서 잘라온 것(doc_figures, 환각 0). description은 주변 원문 근거로
// 생성한 AI 설명(Layer 2+) — "설명 + 그림"으로 이해를 돕는다.
export function ImageBlock({ data }: { data: ImageBlockData }) {
  const [failed, setFailed] = useState(false);
  const src = `${apiBaseUrl}/api/documents/figures/${data.figureId}`;

  return (
    <figure>
      {/* AI 그림 설명 — 그림 위에 먼저 두어 "무엇을 볼지" 안내 */}
      {data.description && (
        <div className="mb-3 flex gap-2 rounded-xl border-l-4 border-accent bg-accent/5 p-3.5">
          <SparkleIcon weight="fill" className="mt-0.5 shrink-0 text-accent" />
          <p className="break-keep text-[0.95rem] leading-[1.7] text-text-secondary">
            {data.description}
          </p>
        </div>
      )}
      {failed ? (
        <div className="flex items-center justify-center gap-2 rounded-xl border border-dashed border-border-primary bg-bg-secondary/50 py-10 text-text-tertiary">
          <ImageBrokenIcon className="text-2xl" />
          그림을 불러오지 못했어요
        </div>
      ) : (
        <img
          src={src}
          alt={data.description ?? data.caption ?? "교재 그림"}
          loading="lazy"
          onError={() => setFailed(true)}
          className="mx-auto max-h-[420px] max-w-full rounded-xl border border-border-primary bg-white object-contain"
        />
      )}
      <figcaption className="mt-2 flex items-center justify-between text-[0.82rem] text-text-tertiary">
        <span>{data.caption ?? "교재 원문 그림"}</span>
        {data.page != null && <span>교재 {data.page}쪽</span>}
      </figcaption>
    </figure>
  );
}
