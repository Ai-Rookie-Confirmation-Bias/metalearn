import { useState } from "react";
import { ImageBrokenIcon } from "@phosphor-icons/react";

import { apiBaseUrl } from "@/shared/api/client";

import type { ImageBlockData } from "./types";

// ① 교재 그림 블록 — 읽기만, 추적 없음(onAnswer 없음).
// AI가 그린 게 아니라 원문에서 잘라온 그림(doc_figures) — 환각 0, 그림 자체가 근거.
// 로드 실패 시 자리 표시(빈 화면 금지) — 서버가 지워졌거나 네트워크 문제일 때.
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
    </figure>
  );
}
