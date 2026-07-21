import { useState } from "react";
import {
  BookOpenIcon,
  GlobeSimpleIcon,
  RobotIcon,
  XIcon,
} from "@phosphor-icons/react";

import { getChunkEvidence, type ChunkEvidence } from "@/features/learning/api/chunkEvidence";

import type { LearningBlock } from "./types";

// 근거 배지 — "이 내용은 지어낸 게 아니라 ○○ 근거가 있다"를 블록 하단에 표시.
// 생성 파이프라인이 근거 없는 블록을 폐기(verified=true만 서빙)하므로, 그 근거를
// 사용자에게 보이게 하는 마지막 조각. book=교재 페이지 / ai_prereq=외부 출처 링크.
// 교재 배지는 클릭하면 "근거 보기" 팝업으로 원문 청크를 즉석에서 보여준다
// (추적 가능한 AI — GPT와의 핵심 차별을 화면으로 증명).
export function EvidenceBadge({ block }: { block: LearningBlock }) {
  const [open, setOpen] = useState(false);
  const [chunks, setChunks] = useState<ChunkEvidence[] | null>(null);
  const [loading, setLoading] = useState(false);

  // analogy는 검증 면제(발판)라 근거 배지를 붙이지 않는다 — source 배지로 충분.
  if (block.source === "analogy") return null;

  const pages = block.sourcePages ?? [];
  const refs = block.externalRefs ?? [];
  const chunkIds = block.sourceChunkIds ?? [];
  const PAGE_MAX = 5;
  const pageLabel =
    pages.length > 0 && pages.length <= PAGE_MAX
      ? pages[0] === pages[pages.length - 1]
        ? `${pages[0]}쪽`
        : `${pages[0]}–${pages[pages.length - 1]}쪽`
      : null;

  if (!pageLabel && refs.length === 0) return null;

  const openEvidence = async () => {
    setOpen(true);
    if (chunks || chunkIds.length === 0) return;
    setLoading(true);
    try {
      setChunks(await getChunkEvidence(chunkIds));
    } catch {
      setChunks([]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="mt-5 flex flex-wrap items-center gap-2 border-t border-border-primary pt-3 text-[0.78rem]">
      <span className="font-semibold text-text-tertiary">근거</span>

      {/* book — 교재 페이지. 클릭하면 원문 청크 팝업(근거 보기) */}
      {pageLabel && (
        <button
          type="button"
          onClick={openEvidence}
          disabled={chunkIds.length === 0}
          className="inline-flex items-center gap-1.5 rounded-full bg-[#6366f1]/10 px-2.5 py-1 font-medium text-[#4f46e5] transition-colors hover:bg-[#6366f1]/20 disabled:cursor-default disabled:hover:bg-[#6366f1]/10"
          title={chunkIds.length ? "교재 원문 보기" : undefined}
        >
          <BookOpenIcon weight="fill" />
          교재 {pageLabel}
          {chunkIds.length > 0 && <span className="opacity-60">· 원문 보기</span>}
        </button>
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

      {/* 근거 보기 팝업 — 배지가 가리키는 교재 원문(추적 가능한 AI) */}
      {open && (
        <div
          className="fixed inset-0 z-[1300] flex items-center justify-center bg-black/50 p-4"
          onClick={() => setOpen(false)}
        >
          <div
            className="flex max-h-[80vh] w-full max-w-[720px] flex-col overflow-hidden rounded-2xl bg-white shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between border-b border-border-primary px-6 py-4">
              <div className="flex items-center gap-2 text-[0.95rem] font-bold text-text-primary">
                <BookOpenIcon weight="fill" className="text-[#6366f1]" />
                교재 원문 근거
                {pageLabel && (
                  <span className="text-[0.82rem] font-medium text-text-tertiary">
                    · {pageLabel}
                  </span>
                )}
              </div>
              <button
                type="button"
                onClick={() => setOpen(false)}
                aria-label="닫기"
                className="flex h-8 w-8 items-center justify-center rounded-full text-text-tertiary transition-colors hover:bg-bg-secondary hover:text-text-primary"
              >
                <XIcon weight="bold" />
              </button>
            </div>
            <div className="overflow-y-auto px-6 py-5">
              <p className="mb-4 text-[0.82rem] text-text-tertiary">
                이 학습 내용은 아래 교재 원문에 근거해 생성됐어요 — 지어낸 내용이 아니에요.
              </p>
              {loading ? (
                <div className="py-10 text-center text-text-tertiary">원문 불러오는 중…</div>
              ) : chunks && chunks.length > 0 ? (
                <div className="space-y-4">
                  {chunks.map((c) => (
                    <div
                      key={c.id}
                      className="rounded-xl border border-border-primary bg-bg-secondary/40 p-4"
                    >
                      <div className="mb-2 flex items-center gap-2 text-[0.78rem] font-semibold text-text-secondary">
                        {c.pageFrom != null && (
                          <span className="rounded bg-[#6366f1]/10 px-2 py-0.5 text-[#4f46e5]">
                            교재 {c.pageFrom === c.pageTo || c.pageTo == null
                              ? `${c.pageFrom}쪽`
                              : `${c.pageFrom}–${c.pageTo}쪽`}
                          </span>
                        )}
                        {c.heading && <span className="truncate">{c.heading}</span>}
                      </div>
                      <div className="whitespace-pre-wrap break-keep text-[0.9rem] leading-[1.7] text-text-secondary">
                        {c.content.replace(/!\[image\]\([^)]*\)/g, "").trim()}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="py-10 text-center text-text-tertiary">
                  원문을 불러오지 못했어요.
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
