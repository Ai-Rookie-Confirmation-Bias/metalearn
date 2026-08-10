// 화면 하나를 **개념 단위 덩이**로 자른다.
//
// 한 덩이 = [그 개념 설명 · 그 개념 그림 · 그 개념 빈칸]. 일반 학습 화면과
// 몰입 뷰어가 **같은 규칙**을 써야 한다 — 두 곳에서 각자 자르면 같은 화면인데
// 몰입 모드에서만 순서가 다르거나 그림이 빠지는 일이 생긴다.
import type { BlockOut, FigureOut, LessonOut } from "@/features/curriculum/api/curriculum";

export type LessonStep = {
  /** 이 덩이의 개념. null이면 어디에도 못 붙은 것들을 모아 둔 마지막 덩이. */
  key: string | null;
  explain?: BlockOut;
  figures: FigureOut[];
  blocks: BlockOut[];
  /** 빈칸 번호를 화면 전체에서 이어 붙이기 위한 시작값. */
  offset: number;
};

export type LessonParts = {
  steps: LessonStep[];
  /** 개념에 못 붙은 설명(옛 응답·이름 불일치). 맨 앞에 그대로 둔다. */
  looseExplain: BlockOut[];
  analogy?: BlockOut;
  tieIn?: BlockOut;
  mcq?: BlockOut;
};

export function splitLesson(data: LessonOut): LessonParts {
  const analogy = data.blocks.find((b) => b.type === "analogy");
  const tieIn = data.blocks.find((b) => b.type === "tie_in");
  const mcq = data.blocks.find((b) => b.type === "mcq");

  // 설명은 개념마다 한 블록이다(백엔드 `sections` 스키마). concept_keys가
  // 여럿인 것은 옛 응답이거나 이름이 안 맞은 덩이라 loose로 뺀다.
  const explainByConcept = new Map<string, BlockOut>();
  const looseExplain: BlockOut[] = [];
  for (const b of data.blocks) {
    if (b.type !== "concept") continue;
    const key = b.conceptKeys.length === 1 ? b.conceptKeys[0] : null;
    if (key && data.concepts.includes(key)) explainByConcept.set(key, b);
    else looseExplain.push(b);
  }

  // 빈칸도 같은 규칙. 귀속이 애매한 것(개념 여럿/없음)은 맨 뒤 한 묶음.
  const byConcept = new Map<string, BlockOut[]>();
  const rest: BlockOut[] = [];
  for (const b of data.blocks) {
    if (b.type !== "cloze") continue;
    const key = b.conceptKeys.length === 1 ? b.conceptKeys[0] : null;
    if (key && data.concepts.includes(key)) {
      byConcept.set(key, [...(byConcept.get(key) ?? []), b]);
    } else {
      rest.push(b);
    }
  }

  const figs = data.figures ?? [];
  const figByConcept = new Map<string, FigureOut[]>();
  for (const f of figs) {
    const key = f.conceptKey;
    if (!key || !data.concepts.includes(key)) continue;
    figByConcept.set(key, [...(figByConcept.get(key) ?? []), f]);
  }
  const looseFigs = figs.filter(
    (f) => !f.conceptKey || !data.concepts.includes(f.conceptKey),
  );

  let n = 0;
  const steps: LessonStep[] = [];
  for (const key of data.concepts) {
    const blocks = byConcept.get(key) ?? [];
    const explain = explainByConcept.get(key);
    const figures = figByConcept.get(key) ?? [];
    // 셋 중 하나라도 있으면 덩이를 만든다 — 그림이 없으면 그냥 안 넣는다.
    if (!blocks.length && !explain && !figures.length) continue;
    steps.push({ key, explain, figures, blocks, offset: n });
    n += blocks.length;
  }
  if (rest.length || looseFigs.length) {
    steps.push({ key: null, figures: looseFigs, blocks: rest, offset: n });
  }

  return { steps, looseExplain, analogy, tieIn, mcq };
}
