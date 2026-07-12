import { Fragment, type ReactNode } from "react";
import { clsx } from "clsx";

// LLM이 생성한 본문 텍스트 렌더러 — 줄바꿈을 살려 "텍스트 벽"을 문단으로 푼다.
//   - 빈 줄(\n\n)은 문단 간격, 단일 \n은 줄바꿈으로.
//   - **강조**는 <strong>, `코드`는 <code> (mock 수준의 최소 인라인 파서).
// 렌더 지점(개념 본문·비유·해설·재설명 등)마다 파서를 중복 구현하지 않기 위한 공용 유틸.
function inline(text: string, keyBase: string): ReactNode[] {
  // **bold** 우선 분리 → 홀수 인덱스가 강조
  return text.split(/\*\*(.+?)\*\*/g).map((part, i) => {
    if (i % 2 === 1) {
      return (
        <strong key={`${keyBase}-b${i}`} className="font-bold text-text-primary">
          {part}
        </strong>
      );
    }
    // 나머지에서 `code` 분리 → 홀수 인덱스가 코드
    return part.split(/`(.+?)`/g).map((p, j) =>
      j % 2 === 1 ? (
        <code
          key={`${keyBase}-c${i}-${j}`}
          className="rounded bg-bg-secondary px-1.5 py-0.5 font-mono text-[0.9em] text-text-primary"
        >
          {p}
        </code>
      ) : (
        <Fragment key={`${keyBase}-t${i}-${j}`}>{p}</Fragment>
      ),
    );
  });
}

export function Prose({ text, className }: { text: string; className?: string }) {
  // 빈 줄 기준 문단 분리(연속 개행·공백 줄 허용), 문단 안의 단일 \n은 <br>로.
  const paragraphs = text
    .split(/\n\s*\n/)
    .map((p) => p.trim())
    .filter(Boolean);

  return (
    <div className={clsx("break-keep", className)}>
      {paragraphs.map((para, pi) => (
        <p key={pi} className={pi > 0 ? "mt-4" : undefined}>
          {para.split("\n").map((line, li, arr) => (
            <Fragment key={li}>
              {inline(line, `${pi}-${li}`)}
              {li < arr.length - 1 && <br />}
            </Fragment>
          ))}
        </p>
      ))}
    </div>
  );
}
