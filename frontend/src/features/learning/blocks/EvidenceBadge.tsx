import { BookOpenIcon, GlobeSimpleIcon, RobotIcon } from "@phosphor-icons/react";

import type { LearningBlock } from "./types";

// 근거 배지 — "이 내용은 지어낸 게 아니라 ○○ 근거가 있다"를 블록 하단에 표시.
// 생성 파이프라인이 근거 없는 블록을 폐기(verified=true만 서빙)하므로, 그 근거를
// 사용자에게 보이게 하는 마지막 조각. book=교재 페이지 / ai_prereq=외부 출처 링크.
export function EvidenceBadge({ block }: { block: LearningBlock }) {
  // analogy는 검증 면제(발판)라 근거 배지를 붙이지 않는다 — source 배지로 충분.
  if (block.source === "analogy") return null;

  const pages = block.sourcePages ?? [];
  const refs = block.externalRefs ?? [];
  const pageLabel =
    pages.length > 0
      ? pages[0] === pages[pages.length - 1]
        ? `${pages[0]}쪽`
        : `${pages[0]}–${pages[pages.length - 1]}쪽`
      : null;

  if (!pageLabel && refs.length === 0) return null;

  return (
    <div className="mt-5 flex flex-wrap items-center gap-2 border-t border-border-primary pt-3 text-[0.78rem]">
      <span className="font-semibold text-text-tertiary">근거</span>

      {/* book — 교재 페이지 범위 */}
      {pageLabel && (
        <span className="inline-flex items-center gap-1.5 rounded-full bg-[#6366f1]/10 px-2.5 py-1 font-medium text-[#4f46e5]">
          <BookOpenIcon weight="fill" />
          교재 {pageLabel}
        </span>
      )}

      {/* ai_prereq — 외부 출처(위키 등). url 있으면 링크, llm 폴백이면 정적 배지 */}
      {refs.map((ref, i) => {
        const label = ref.title || (ref.kind === "web" ? "웹 출처" : "AI 요약");
        const Icon = ref.kind === "web" || ref.url ? GlobeSimpleIcon : RobotIcon;
        const cls =
          "inline-flex max-w-[220px] items-center gap-1.5 rounded-full bg-accent/10 px-2.5 py-1 font-medium text-accent";
        return ref.url ? (
          <a
            key={i}
            href={ref.url}
            target="_blank"
            rel="noopener noreferrer"
            className={`${cls} transition-colors hover:bg-accent/20`}
            title={ref.title}
          >
            <Icon weight="fill" className="shrink-0" />
            <span className="truncate">{label}</span>
          </a>
        ) : (
          <span key={i} className={cls} title={ref.title}>
            <Icon weight="fill" className="shrink-0" />
            <span className="truncate">{label}</span>
          </span>
        );
      })}
    </div>
  );
}
