// 빈칸 하나 — 학습 화면과 복습이 같이 쓴다.
//
// 복습에도 같은 컴포넌트를 쓰는 이유: 채점 규칙(accept 표기 흔들림 흡수)과
// 기록 규칙(개념이 하나로 특정될 때만 그 개념에 붙인다)이 같아야 한다.
// 화면마다 따로 두면 한쪽만 고쳐져 숙련도가 갈린다.
import { useState } from "react";

import type { BlockOut } from "@/features/curriculum/api/curriculum";

/** 표기 흔들림만 흡수한다. 인정할 답 목록은 백엔드가 정해서 `accept`로 보낸다. */
const norm = (s: string) => s.replace(/\s+/g, "").toLowerCase();

export function Cloze({
  block,
  index,
  onGraded,
}: {
  block: BlockOut;
  index: number;
  onGraded: (correct: boolean, conceptKey?: string) => void;
}) {
  const sentence = String(block.content.sentence ?? "");
  const answer = String(block.content.answer ?? "");
  // 백엔드가 정해준 인정 표기들. `폭포수 모형`의 정답에 `폭포수`도 들어 있다.
  const accept = (block.content.accept as string[] | undefined) ?? [answer];
  const [value, setValue] = useState("");
  const [graded, setGraded] = useState<boolean | null>(null);

  const check = () => {
    if (graded !== null || !value.trim()) return;
    const ok = accept.some((a) => norm(a) === norm(value));
    setGraded(ok);
    // 개념이 하나로 특정될 때만 그 개념에 기록한다. 여럿이면(라벨을 못 붙인 경우)
    // 절 단위로만 센다 — 첫 개념에 몰아주면 약점 통계가 통째로 거짓이 된다.
    onGraded(ok, block.conceptKeys.length === 1 ? block.conceptKeys[0] : undefined);
  };

  const [before, after] = sentence.split("____");
  return (
    <li className="rounded-lg border border-border-primary p-4">
      <p className="text-[0.7rem] font-semibold text-text-tertiary">빈칸 {index}</p>
      <p className="mt-1 leading-relaxed text-text-primary">
        {before}
        <span className="mx-1 inline-block min-w-[5rem] border-b-2 border-accent text-center font-semibold text-accent">
          {graded !== null ? answer : "　　　"}
        </span>
        {after}
      </p>

      {graded === null ? (
        <div className="mt-3 flex gap-2">
          <input
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && check()}
            placeholder="답을 적어보세요"
            className="flex-1 rounded border border-border-primary px-3 py-1.5 text-sm outline-none focus:border-accent"
          />
          <button
            type="button"
            onClick={check}
            className="rounded bg-primary px-3 py-1.5 text-sm font-medium text-white hover:bg-primary-hover"
          >
            확인
          </button>
        </div>
      ) : (
        <p
          className={`mt-2 text-sm font-semibold ${graded ? "text-emerald-600" : "text-red-600"}`}
        >
          {graded ? "✓ 맞았습니다" : `✗ 정답은 "${answer}" 입니다`}
          {!graded && value && (
            <span className="ml-1 font-normal text-text-tertiary">(적은 답: {value})</span>
          )}
        </p>
      )}
    </li>
  );
}

