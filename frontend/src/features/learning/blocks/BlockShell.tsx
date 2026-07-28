import type { ReactNode } from "react";
import { clsx } from "clsx";
import { BookOpenIcon, RobotIcon, LightbulbIcon } from "@phosphor-icons/react";

import type { ContentSource } from "./types";

// 출처 배지 — 📖 교재(indigo) / 🤖 AI 생성(accent) / 💡 비유(violet)
const SOURCE_BADGE: Record<ContentSource, { icon: typeof BookOpenIcon; label: string; bg: string }> = {
  book: { icon: BookOpenIcon, label: "교재 출처", bg: "bg-[#6366f1]" },
  ai_prereq: { icon: RobotIcon, label: "AI 생성", bg: "bg-accent" },
  analogy: { icon: LightbulbIcon, label: "비유", bg: "bg-[#8b5cf6]" },
};

// 모든 블록의 공통 껍데기 (.learning-block: 흰 카드 + 우상단 출처 배지 + 제목)
export function BlockShell({
  source,
  title,
  children,
}: {
  source: ContentSource;
  title?: string;
  children: ReactNode;
}) {
  const badge = SOURCE_BADGE[source];
  const BadgeIcon = badge.icon;

  return (
    <div className="relative mb-6 rounded-2xl border border-border-primary bg-white p-8 shadow-sm transition-colors hover:border-[#d1d5db]">
      <div
        className={clsx(
          "absolute -top-2.5 right-5 flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-bold text-white",
          badge.bg,
        )}
      >
        <BadgeIcon weight="fill" />
        {badge.label}
      </div>
      {title && <h3 className="mb-4 text-xl font-bold text-primary">{title}</h3>}
      {children}
    </div>
  );
}
