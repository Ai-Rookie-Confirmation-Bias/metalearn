import type { ReactNode } from "react";
import { FlaskIcon, TargetIcon, WarningCircleIcon } from "@phosphor-icons/react";

import { Prose } from "@/shared/ui/Prose";

import type { ConceptBlockData } from "./types";

// 구조화 필드 콜아웃 — 필드별 색·아이콘이 다른 박스(AnalogyBlock과 같은 좌측 보더 idiom).
// 텍스트 벽 해소: 정의(body)는 본문, 왜 중요한가/예시/오해는 시각적으로 구분된 박스로.
function Callout({
  icon,
  label,
  color,
  children,
}: {
  icon: ReactNode;
  label: string;
  color: string; // hex — 보더·라벨·배경 틴트에 공통 사용
  children: ReactNode;
}) {
  return (
    <div
      className="mt-4 rounded-xl border-l-4 p-4"
      style={{ borderLeftColor: color, backgroundColor: `${color}0d` }}
    >
      <span
        className="mb-1.5 inline-flex items-center gap-1.5 text-xs font-bold"
        style={{ color }}
      >
        {icon}
        {label}
      </span>
      {children}
    </div>
  );
}

// ① 설명 블록 — 읽기만, 추적 없음(onAnswer 없음).
// 본문은 Prose로: 줄바꿈을 문단으로 살리고 **강조**·`코드`를 렌더(텍스트 벽 해소).
export function ConceptBlock({ data }: { data: ConceptBlockData }) {
  const proseClass = "text-[0.98rem] leading-[1.75] text-text-secondary";
  return (
    <div>
      <Prose
        text={data.body}
        className="text-[1.05rem] leading-[1.8] text-text-secondary"
      />
      {data.whyItMatters && (
        <Callout icon={<TargetIcon weight="fill" />} label="왜 중요할까" color="#6366f1">
          <Prose text={data.whyItMatters} className={proseClass} />
        </Callout>
      )}
      {data.example && (
        <Callout icon={<FlaskIcon weight="fill" />} label="예시" color="#10b981">
          <Prose text={data.example} className={proseClass} />
        </Callout>
      )}
      {data.misconception && (
        <Callout icon={<WarningCircleIcon weight="fill" />} label="흔한 오해" color="#f59e0b">
          <Prose text={data.misconception} className={proseClass} />
        </Callout>
      )}
    </div>
  );
}
