import type { TableBlockData } from "./types";

// ① 비교표 블록 — 읽기만, 추적 없음(onAnswer 없음).
// 서버가 {columns, rows} JSON을 검증해 보내고(HTML 생성 금지) 표는 여기서 그린다.
// 나열·비교 개념(종류·계층·단계별 특징)을 문단 대신 표로 — 텍스트 벽 해소.
export function TableBlock({ data }: { data: TableBlockData }) {
  return (
    <div>
      <div className="overflow-x-auto rounded-xl border border-border-primary">
        <table className="w-full border-collapse text-[0.95rem]">
          <thead>
            <tr className="bg-bg-secondary">
              {data.columns.map((col, i) => (
                <th
                  key={i}
                  className="border-b-2 border-border-primary px-4 py-2.5 text-left font-bold text-text-primary"
                >
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.rows.map((row, ri) => (
              <tr key={ri} className={ri % 2 === 1 ? "bg-bg-secondary/40" : undefined}>
                {row.map((cell, ci) => (
                  <td
                    key={ci}
                    className={
                      "break-keep border-b border-border-primary px-4 py-2.5 align-top leading-[1.6] text-text-secondary " +
                      (ci === 0 ? "font-semibold text-text-primary" : "")
                    }
                  >
                    {cell}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {data.caption && (
        <p className="mt-2 text-[0.82rem] text-text-tertiary">{data.caption}</p>
      )}
    </div>
  );
}
