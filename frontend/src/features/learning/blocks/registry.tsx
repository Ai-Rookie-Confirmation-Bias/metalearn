import { WarningCircleIcon } from "@phosphor-icons/react";

import type { LearningBlock, OnAnswer } from "./types";
import { BlockShell } from "./BlockShell";
import { ConceptBlock } from "./ConceptBlock";
import { ClozeBlock } from "./ClozeBlock";
import { McqBlock } from "./McqBlock";
import { ExplainBackBlock } from "./ExplainBackBlock";

// type → 렌더러. 새 블록 = types.ts에 data 추가 + 여기 case 추가가 전부.
// (진단·복습·연결도 같은 봉투 type이라 이 함수 하나가 모든 화면의 토대)
function renderBody(block: LearningBlock, onAnswer: OnAnswer) {
  switch (block.type) {
    case "concept":
      return <ConceptBlock data={block.data} />;
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
  return (
    <BlockShell source={block.source} title={block.data.title}>
      {body}
    </BlockShell>
  );
}
