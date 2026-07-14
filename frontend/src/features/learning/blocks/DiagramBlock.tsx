import { useEffect, useState } from "react";
import { ArrowRightIcon } from "@phosphor-icons/react";

import type { DiagramBlockData, DiagramEdge, DiagramNode } from "./types";

// mermaid는 번들이 커서(수백 KB) 첫 diagram 블록에서만 dynamic import — 모듈 1회 로드.
let mermaidPromise: Promise<typeof import("mermaid")["default"]> | null = null;
function loadMermaid() {
  mermaidPromise ??= import("mermaid").then((m) => {
    m.default.initialize({
      startOnLoad: false,
      securityLevel: "strict",
      theme: "neutral",
      fontFamily: "inherit",
    });
    return m.default;
  });
  return mermaidPromise;
}

// 렌더 실패 폴백 — 서버가 구조화 데이터(nodes/edges)를 함께 저장해둔 덕에
// mermaid가 죽어도 학습 내용(관계)은 리스트로 전달된다. 절대 빈 화면 금지.
function FallbackList({ nodes, edges }: { nodes: DiagramNode[]; edges: DiagramEdge[] }) {
  const label = new Map(nodes.map((n) => [n.id, n.label]));
  return (
    <ul className="space-y-2">
      {edges.map((e, i) => (
        <li key={i} className="flex flex-wrap items-center gap-2 text-[0.98rem] text-text-secondary">
          <span className="rounded-lg bg-bg-secondary px-2.5 py-1 font-semibold text-text-primary">
            {label.get(e.source) ?? e.source}
          </span>
          <ArrowRightIcon className="shrink-0 text-text-tertiary" />
          <span className="rounded-lg bg-bg-secondary px-2.5 py-1 font-semibold text-text-primary">
            {label.get(e.target) ?? e.target}
          </span>
          {e.label && <span className="text-[0.85rem] text-text-tertiary">— {e.label}</span>}
        </li>
      ))}
    </ul>
  );
}

// ① 다이어그램 블록 — 읽기만, 추적 없음(onAnswer 없음).
// 서버가 그래프 JSON을 검증·조립한 mermaid를 그린다. parse가 2차 방어선,
// 실패하면 구조화 폴백 리스트(1차 게이트가 서버라 여긴 거의 안 온다).
export function DiagramBlock({ blockId, data }: { blockId: string; data: DiagramBlockData }) {
  const [svg, setSvg] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    const code = data.mermaid;
    if (!code) {
      setFailed(true);
      return;
    }
    let alive = true;
    loadMermaid()
      .then(async (mermaid) => {
        await mermaid.parse(code); // 2차 방어선 — 실패 시 throw → 폴백
        const id = `mmd-${blockId.replace(/[^a-zA-Z0-9]/g, "")}`;
        const { svg: rendered } = await mermaid.render(id, code);
        if (alive) setSvg(rendered);
      })
      .catch(() => {
        if (alive) setFailed(true);
      });
    return () => {
      alive = false;
    };
  }, [blockId, data.mermaid]);

  return (
    <div>
      {failed ? (
        <FallbackList nodes={data.nodes} edges={data.edges} />
      ) : svg ? (
        // mermaid 출력은 securityLevel:"strict"로 새니타이즈된 자체 생성 SVG
        <div
          className="flex justify-center overflow-x-auto [&_svg]:h-auto [&_svg]:max-w-full"
          dangerouslySetInnerHTML={{ __html: svg }}
        />
      ) : (
        <div className="h-24 animate-pulse rounded-xl bg-bg-secondary" />
      )}
      {data.caption && (
        <p className="mt-2 text-[0.82rem] text-text-tertiary">{data.caption}</p>
      )}
    </div>
  );
}
