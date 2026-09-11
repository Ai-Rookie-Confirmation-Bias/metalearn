// 설명 본문. 줄글과 **마크다운 파이프 표**를 섞어서 그린다.
//
// ## 왜 마크다운 라이브러리를 안 쓰나
//
// 여기서 그려야 하는 마크다운은 사실상 표 하나다. 진단 성향 `table`을 고른
// 학습자에게만 생성기가 표를 내고(`STYLE_DIRECTIVE.table`), 나머지 셋은
// 줄글이다. 그 한 가지 때문에 파서를 통째로 들이면 링크·이미지·HTML까지
// 딸려 들어와 **교재 원문이 아닌 것이 원문처럼 보일 길**이 생긴다.
//
// ⚠️ 이게 없을 때 `table` 성향은 **끝까지 갈 길이 없었다.** 본문을
//    `whitespace-pre-line`으로만 그려서, 생성기가 표를 내도 화면에는
//    `| 항목 | 설명 |`이 글자 그대로 보였다. 지시문은 있는데 화면이 못 받는
//    자리였다 — 성향 넷 중 하나가 조용히 죽어 있었다.
import { Fragment } from "react";

// 파이프 표의 구분선. `|---|:--:|` 같은 것.
const DIVIDER = /^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$/;

function isRow(line: string): boolean {
  return line.trimStart().startsWith("|") && line.includes("|", 1);
}

function cells(line: string): string[] {
  const t = line.trim();
  // 양끝 파이프는 칸이 아니다 — 떼고 나눈다.
  return t
    .slice(t.startsWith("|") ? 1 : 0, t.endsWith("|") ? -1 : undefined)
    .split("|")
    .map((c) => c.trim());
}

type Chunk = { kind: "text"; lines: string[] } | { kind: "table"; rows: string[][] };

// 본문을 줄글 덩어리와 표 덩어리로 가른다.
//
// 표로 인정하는 조건은 **머리행 + 구분선**이다. 구분선을 요구하는 이유:
// 줄글에 파이프가 하나 섞였다고 표로 그려 버리면 문장이 칸으로 찢어진다.
export function split(text: string): Chunk[] {
  const lines = text.split("\n");
  const out: Chunk[] = [];
  let buf: string[] = [];

  const flush = () => {
    if (buf.length) out.push({ kind: "text", lines: buf });
    buf = [];
  };

  for (let i = 0; i < lines.length; i++) {
    if (isRow(lines[i]) && i + 1 < lines.length && DIVIDER.test(lines[i + 1])) {
      flush();
      const rows = [cells(lines[i])];
      i += 2; // 머리행과 구분선을 건너뛴다
      while (i < lines.length && isRow(lines[i])) rows.push(cells(lines[i++]));
      i--; // for가 다시 올린다
      out.push({ kind: "table", rows });
      continue;
    }
    buf.push(lines[i]);
  }
  flush();
  return out;
}

function Table({ rows }: { rows: string[][] }) {
  const [head, ...body] = rows;
  return (
    // 좁은 화면에서 표가 본문을 밀지 않게 스크롤은 표 안에서 처리한다.
    <div className="my-4 overflow-x-auto">
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr>
            {head.map((c, i) => (
              <th
                key={i}
                className="border border-border-primary bg-bg-secondary px-3 py-2 text-left font-semibold"
              >
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {body.map((row, r) => (
            <tr key={r}>
              {row.map((c, i) => (
                <td key={i} className="border border-border-primary px-3 py-2 align-top">
                  {c}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function Explanation({ text }: { text: string }) {
  return (
    <article className="mb-5 leading-loose text-text-primary">
      {split(text).map((chunk, i) => (
        <Fragment key={i}>
          {chunk.kind === "table" ? (
            <Table rows={chunk.rows} />
          ) : (
            <p className="whitespace-pre-line">{chunk.lines.join("\n")}</p>
          )}
        </Fragment>
      ))}
    </article>
  );
}
