// 객관식 문항 하나 — 학습 화면과 단원 평가가 같이 쓴다.
//
// 두 곳에서 목적이 다르다:
//   학습    이 화면 개념들 사이를 가를 수 있나
//   평가    단원 전체를 가로질러 가를 수 있나
// 다만 **푸는 경험은 같아야** 한다. 평가라고 모양이 달라지면 학습자가 새로 배운다.
import { useState } from "react";

import type { BlockOut } from "@/features/curriculum/api/curriculum";

export function Mcq({
  block,
  label = "구별하기 — 헷갈리는 지점",
  onGraded,
}: {
  block: BlockOut;
  label?: string;
  onGraded: (correct: boolean, conceptKey?: string) => void;
}) {
  const question = String(block.content.question ?? "");
  const options = (block.content.options as string[]) ?? [];
  const answer = String(block.content.answer ?? "");
  const explanation = String(block.content.explanation ?? "");
  const [picked, setPicked] = useState<string | null>(null);

  // 객관식은 여러 개념을 구별하는 문항이라 conceptKeys가 묶음 전체다.
  // **채점 귀속에 conceptKeys[0]을 쓰면 안 된다** — 항상 첫 개념에 몰린다
  // (실측 5/5 오귀속). 백엔드가 "이 문항이 실제로 묻는 개념"을 content.concept로
  // 실어 보낸다.
  const target = (block.content.concept as string | null) ?? undefined;

  const pick = (o: string) => {
    if (picked !== null) return;
    setPicked(o);
    onGraded(o === answer, target);
  };

  return (
    <li className="rounded-lg border border-border-primary p-4">
      <p className="text-[0.7rem] font-semibold text-text-tertiary">{label}</p>
      <p className="mt-1 leading-relaxed font-medium text-text-primary">{question}</p>
      <ul className="mt-3 space-y-1.5">
        {options.map((o) => {
          const isAnswer = o === answer;
          const chosen = picked === o;
          const done = picked !== null;
          return (
            <li key={o}>
              <button
                type="button"
                disabled={done}
                onClick={() => pick(o)}
                className={[
                  "w-full rounded border px-3 py-2 text-left text-sm transition-colors",
                  !done && "border-border-primary hover:bg-bg-secondary",
                  done && isAnswer && "border-emerald-400 bg-emerald-50 font-semibold",
                  done && chosen && !isAnswer && "border-red-400 bg-red-50",
                  done && !isAnswer && !chosen && "border-border-primary opacity-50",
                ]
                  .filter(Boolean)
                  .join(" ")}
              >
                {done && isAnswer && "✓ "}
                {done && chosen && !isAnswer && "✗ "}
                {o}
              </button>
            </li>
          );
        })}
      </ul>
      {/* 형성평가에서 특히 중요하다 — 점수를 매기는 자리가 아니라
          **가르는 법을 배우는 자리**라, 왜 나머지가 아닌지가 본론이다. */}
      {picked !== null && explanation && (
        <p className="mt-3 text-sm leading-relaxed text-text-secondary">{explanation}</p>
      )}
    </li>
  );
}
