// 교재에 실려 있던 그림.
//
// 📎 원문과 같은 이유로 보여준다 — **AI가 그린 게 아니라 교재의 그 그림**이라는
// 게 설명의 근거다. 그래서 캡션 대신 쪽수를 적는다(캡션은 파싱이 못 찾는 일이
// 많고, 쪽수는 항상 있다).
//
// `needsVision`은 파싱이 "텍스트만으로는 불완전하다"고 본 그림이다. 그 경우
// 설명이 그림을 대신할 수 없다는 뜻이라 크게 놓는다.
import { useState } from "react";
import { clsx } from "clsx";

import { apiBaseUrl } from "@/shared/api/client";
import type { FigureOut } from "@/features/curriculum/api/curriculum";

function One({ figure }: { figure: FigureOut }) {
  const [failed, setFailed] = useState(false);
  if (failed) return null;

  return (
    <figure
      className={clsx(
        "overflow-hidden rounded-xl border border-border-primary bg-white",
        figure.needsVision ? "col-span-full" : "",
      )}
    >
      <img
        src={`${apiBaseUrl}${figure.url}`}
        alt={figure.caption || `교재 p.${figure.page} 그림`}
        // lazy를 안 쓴다 — 한 화면에 많아야 서너 장이라 아낄 게 없고, 스크롤한
        // 뒤에 늦게 뜨면 설명과 그림이 따로 노는 것처럼 보인다.
        onError={() => setFailed(true)}
        className="w-full object-contain"
      />
      <figcaption className="border-t border-border-primary px-3 py-1.5 text-[0.72rem] text-text-tertiary">
        📖 교재 p.{figure.page}
        {figure.caption && <> · {figure.caption}</>}
      </figcaption>
    </figure>
  );
}

export function Figures({ figures }: { figures: FigureOut[] }) {
  if (figures.length === 0) return null;
  return (
    <div
      className={clsx(
        "mb-5 grid gap-3",
        figures.length > 1 ? "sm:grid-cols-2" : "grid-cols-1",
      )}
    >
      {figures.map((f) => (
        <One key={f.figureId} figure={f} />
      ))}
    </div>
  );
}
