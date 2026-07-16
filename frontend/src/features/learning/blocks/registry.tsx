import { ClockCounterClockwiseIcon, WarningCircleIcon } from "@phosphor-icons/react";

import type { LearningBlock, OnAnswer } from "./types";
import { BlockShell } from "./BlockShell";
import { ConceptBlock } from "./ConceptBlock";
import { TableBlock } from "./TableBlock";
import { ImageBlock } from "./ImageBlock";
import { DiagramBlock } from "./DiagramBlock";
import { ClozeBlock } from "./ClozeBlock";
import { McqBlock } from "./McqBlock";
import { ExplainBackBlock } from "./ExplainBackBlock";
import { AnalogyBlock } from "./AnalogyBlock";

// type → 렌더러. 새 블록 = types.ts에 data 추가 + 여기 case 추가가 전부.
// (진단·복습·연결도 같은 봉투 type이라 이 함수 하나가 모든 화면의 토대)
function renderBody(block: LearningBlock, onAnswer: OnAnswer) {
  switch (block.type) {
    case "concept":
      return <ConceptBlock data={block.data} />;
    case "table": // 읽기 전용(tracked 아님) — 비교표
      return <TableBlock data={block.data} />;
    case "image": // 읽기 전용 — 교재 원문 그림(환각 0)
      return <ImageBlock data={block.data} />;
    case "diagram": // 읽기 전용 — 서버 조립 mermaid 렌더 + 구조화 폴백
      return <DiagramBlock blockId={block.id} data={block.data} />;
    case "analogy": // 읽기 전용(tracked 아님) — prereq 절이 비유만 있는 경우가 있어 폴백이 뜨던 타입
      return <AnalogyBlock data={block.data} />;
    case "cloze":
      return (
        <ClozeBlock blockId={block.id} conceptId={block.conceptId} data={block.data} onAnswer={onAnswer} />
      );
    case "mcq":
      return <McqBlock blockId={block.id} conceptId={block.conceptId} data={block.data} onAnswer={onAnswer} />;
    case "explainBack":
      return (
        <ExplainBackBlock blockId={block.id} conceptId={block.conceptId} data={block.data} onAnswer={onAnswer} />
      );
  }
}

// 미지원 type 폴백 — 에러 대신 "표시 불가" 카드 (AI가 새 type을 뱉어도 화면이 안 죽게)
function FallbackBlock({ type }: { type: string }) {
  return (
    <div className="mb-6 flex items-center gap-3 rounded-2xl border-2 border-dashed border-border-primary bg-white/50 p-8 font-semibold text-text-tertiary">
      <WarningCircleIcon className="text-2xl" />
      아직 지원하지 않는 블록이에요 ({type})
    </div>
  );
}

export function BlockRenderer({ block, onAnswer }: { block: LearningBlock; onAnswer: OnAnswer }) {
  // attempts.kind는 봉투가 알고 있으므로 여기서 채워 위로 전달 (기본 learn)
  const answerWithKind: OnAnswer = (e) => onAnswer({ ...e, kind: block.kind ?? "learn" });
  const body = renderBody(block, answerWithKind);
  if (body === undefined) return <FallbackBlock type={(block as { type: string }).type} />;
  // 이유 라벨(변화 가시성): 복습 카드는 왜 나왔는지 서버가 말한다 — 말없이 변하지 않는다
  const reviewReason = block.meta?.reviewReason;
  return (
    <div>
      {reviewReason && (
        <div className="mb-2 flex items-center gap-2 rounded-xl bg-[#0ea5e9]/10 px-4 py-2.5 text-[0.82rem] font-medium text-[#0369a1]">
          <ClockCounterClockwiseIcon weight="fill" className="shrink-0" />
          <span className="rounded-md bg-[#0ea5e9] px-1.5 py-0.5 text-[0.68rem] font-bold text-white">
            복습 카드
          </span>
          {reviewReason}
        </div>
      )}
      <BlockShell source={block.source} title={block.data.title}>
        {body}
      </BlockShell>
    </div>
  );
}
