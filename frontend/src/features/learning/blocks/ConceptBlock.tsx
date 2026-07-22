import type { ReactNode } from "react";
import {
  CheckCircleIcon,
  FlaskIcon,
  FlowArrowIcon,
  TargetIcon,
  WarningCircleIcon,
  XCircleIcon,
} from "@phosphor-icons/react";

import { Prose } from "@/shared/ui/Prose";

import type { ConceptBlockData } from "./types";

// 구조화 필드 콜아웃 — 필드별 색·아이콘이 다른 박스(AnalogyBlock과 같은 좌측 보더 idiom).
// 텍스트 벽 해소: 정의(body)는 본문, 왜 중요한가/예시는 시각적으로 구분된 박스로.
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

// 동작 원리 → 번호가 매겨진 세로 스텝 플로우(문단 대신 시각 흐름).
// 각 단계에 원형 번호 배지 + 다음 단계로 잇는 세로 커넥터.
function StepFlow({ steps }: { steps: string[] }) {
  const accent = "#0ea5e9";
  return (
    <div className="mt-4 rounded-xl border border-border-primary bg-bg-secondary/40 p-4">
      <span
        className="mb-3 inline-flex items-center gap-1.5 text-xs font-bold"
        style={{ color: accent }}
      >
        <FlowArrowIcon weight="fill" /> 동작 흐름
      </span>
      <ol className="flex flex-col">
        {steps.map((s, i) => (
          <li key={i} className="flex gap-3">
            <div className="flex flex-col items-center">
              <span
                className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-[0.8rem] font-bold text-white"
                style={{ backgroundColor: accent }}
              >
                {i + 1}
              </span>
              {i < steps.length - 1 && (
                <span
                  className="my-1 w-px flex-1"
                  style={{ backgroundColor: `${accent}4d` }}
                />
              )}
            </div>
            <span className="break-keep pb-4 pt-1 text-[0.95rem] leading-relaxed text-text-secondary">
              {s}
            </span>
          </li>
        ))}
      </ol>
    </div>
  );
}

// 흔한 오해 → ❌ 오해 / ✅ 실제로는 2단 대비 카드(산문을 시각 대비로).
function MythReality({ myth, reality }: { myth: string; reality: string }) {
  return (
    <div className="mt-4 grid gap-3 sm:grid-cols-2">
      <div className="rounded-xl border-l-4 border-[#ef4444] bg-[#ef4444]/[0.06] p-4">
        <span className="mb-1.5 inline-flex items-center gap-1.5 text-xs font-bold text-[#ef4444]">
          <XCircleIcon weight="fill" /> 흔한 오해
        </span>
        <Prose
          text={myth}
          className="text-[0.92rem] leading-relaxed text-text-secondary"
        />
      </div>
      <div className="rounded-xl border-l-4 border-[#10b981] bg-[#10b981]/[0.06] p-4">
        <span className="mb-1.5 inline-flex items-center gap-1.5 text-xs font-bold text-[#10b981]">
          <CheckCircleIcon weight="fill" /> 실제로는
        </span>
        <Prose
          text={reality}
          className="text-[0.92rem] leading-relaxed text-text-secondary"
        />
      </div>
    </div>
  );
}

// ① 설명 블록 — 읽기만, 추적 없음(onAnswer 없음).
// 본문은 Prose로, 구조화 필드는 전용 그래픽으로: 동작원리=스텝플로우, 오해=❌/✅ 대비.
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
      {data.steps && data.steps.length > 0 && <StepFlow steps={data.steps} />}
      {data.example && (
        <Callout icon={<FlaskIcon weight="fill" />} label="예시" color="#10b981">
          <Prose text={data.example} className={proseClass} />
        </Callout>
      )}
      {/* 오해: 정정(reality)이 함께 오면 ❌/✅ 대비 카드, 아니면 기존 amber 콜아웃(하위호환) */}
      {data.misconception && data.misconceptionReality ? (
        <MythReality myth={data.misconception} reality={data.misconceptionReality} />
      ) : data.misconception ? (
        <Callout icon={<WarningCircleIcon weight="fill" />} label="흔한 오해" color="#f59e0b">
          <Prose text={data.misconception} className={proseClass} />
        </Callout>
      ) : null}
    </div>
  );
}
