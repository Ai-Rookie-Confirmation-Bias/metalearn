// 커리큘럼 화면 공용 조각.
//
// ⚡ 📎 🔒 세 기호는 서비스 정의에서 고정한 시각 언어다.
//   ⚡ AI가 조정한 것 / 📎 원문 근거 / 🔒 잠긴 이유
// 원칙: 규칙이 정한 것만 쓴다. **확신이 없으면 아예 안 쓴다** — 그래서
// reason이 빈 문자열이면 아무것도 렌더하지 않는다(빈 ⚡를 띄우지 않는다).
import { clsx } from "clsx";

import type { MasteryStatus, PlanMode } from "@/features/curriculum/api/curriculum";

const STATUS_STYLE: Record<MasteryStatus, string> = {
  untouched: "bg-bg-secondary text-text-tertiary",
  learning: "bg-blue-50 text-blue-700",
  weak: "bg-red-50 text-red-700",
  shaky: "bg-amber-50 text-amber-700",
  solid: "bg-emerald-50 text-emerald-700",
};

export function StatusBadge({ status, label }: { status: MasteryStatus; label: string }) {
  return (
    <span
      className={clsx(
        "rounded-full px-2 py-0.5 text-[0.7rem] font-semibold whitespace-nowrap",
        STATUS_STYLE[status],
      )}
    >
      {label}
    </span>
  );
}

const MODE_TEXT: Record<PlanMode, string> = {
  deep: "분량 늘림",
  normal: "표준",
  compressed: "핵심만",
};

export function ModeBadge({ mode }: { mode: PlanMode }) {
  if (mode === "normal") return null; // 안 바뀐 걸 표시하면 노이즈다
  return (
    <span
      className={clsx(
        "rounded px-1.5 py-0.5 text-[0.7rem] font-semibold whitespace-nowrap",
        mode === "deep" ? "bg-indigo-50 text-indigo-700" : "bg-slate-100 text-slate-600",
      )}
    >
      {MODE_TEXT[mode]}
    </span>
  );
}

/** ⚡ AI가 왜 이렇게 했는지. 규칙이 만든 문장을 그대로 싣는다. */
export function Reason({ text, tone = "ai" }: { text: string; tone?: "ai" | "quiet" }) {
  if (!text) return null;
  return (
    <p
      className={clsx(
        "flex gap-1.5 text-[0.8rem] leading-relaxed",
        tone === "ai" ? "text-indigo-700" : "text-text-tertiary",
      )}
    >
      <span aria-hidden>⚡</span>
      <span>{text}</span>
    </p>
  );
}

export function Bar({ value, tone = "primary" }: { value: number; tone?: "primary" | "accent" }) {
  return (
    <div className="h-1.5 w-full overflow-hidden rounded-full bg-border-primary">
      <div
        className={clsx(
          "h-full rounded-full transition-all duration-500",
          tone === "accent" ? "bg-accent" : "bg-primary",
        )}
        style={{ width: `${Math.round(Math.min(Math.max(value, 0), 1) * 100)}%` }}
      />
    </div>
  );
}

export const pct = (v: number) => `${Math.round(v * 100)}%`;
