import { useMemo } from "react";
import { useNavigate } from "react-router-dom";

import type { ConceptEdgeItem, ConceptMasteryItem } from "./api/getMastery";

// 지식 지도(B7, 학습 캔버스) — 커리큘럼 대표 개념(절 연결)만 노드로 그린다.
// 열 배치는 depth가 아니라 **선행관계 위상 레이어**(선행이 왼쪽): 대표 개념의
// depth 분포가 좁아(0~1) depth 열은 못 쓴다(실측). 외부 그래프 라이브러리 0 —
// 결정적 레이아웃이라 스냅샷이 안정적이고 번들 비용이 없다.

const NODE_W = 172;
const NODE_H = 46;
const COL_GAP = 84;
const ROW_GAP = 18;
const PAD = 24;

const STATUS_FILL: Record<ConceptMasteryItem["status"], { bg: string; border: string; text: string }> = {
  mastered: { bg: "#d1fae5", border: "#10b981", text: "#065f46" },
  learning: { bg: "#dbeafe", border: "#3b82f6", text: "#1e40af" },
  todo: { bg: "#fef3c7", border: "#f59e0b", text: "#92400e" },
  locked: { bg: "#f3f4f6", border: "#d1d5db", text: "#6b7280" },
};

type LaidNode = ConceptMasteryItem & { x: number; y: number; layer: number };

// 선행관계 longest-path 레이어링: layer(노드) = 1 + max(layer(선행)). 사이클 가드.
function layoutNodes(
  nodes: ConceptMasteryItem[],
  edges: ConceptEdgeItem[],
): { laid: LaidNode[]; width: number; height: number } {
  const ids = new Set(nodes.map((n) => n.conceptId));
  const prereqOf = new Map<string, string[]>(); // 학습대상 → 선행들
  for (const e of edges) {
    if (e.kind !== "prerequisite") continue;
    if (!ids.has(e.fromConceptId) || !ids.has(e.toConceptId)) continue;
    prereqOf.set(e.fromConceptId, [...(prereqOf.get(e.fromConceptId) ?? []), e.toConceptId]);
  }
  const layer = new Map<string, number>();
  const visiting = new Set<string>();
  const layerOf = (id: string): number => {
    const memo = layer.get(id);
    if (memo !== undefined) return memo;
    if (visiting.has(id)) return 0; // 사이클 방어(DAG 규약이지만 데이터 오염 대비)
    visiting.add(id);
    const ps = prereqOf.get(id) ?? [];
    const v = ps.length ? 1 + Math.max(...ps.map(layerOf)) : 0;
    visiting.delete(id);
    layer.set(id, v);
    return v;
  };
  nodes.forEach((n) => layerOf(n.conceptId));

  // 열(레이어)별로 모아 세로 배치 — 같은 열 안에서는 선행들의 평균 y를 따라
  // 정렬(barycenter 1패스)해 교차를 줄인다.
  const cols = new Map<number, ConceptMasteryItem[]>();
  for (const n of nodes) {
    const l = layer.get(n.conceptId) ?? 0;
    cols.set(l, [...(cols.get(l) ?? []), n]);
  }
  const yIndex = new Map<string, number>();
  const laid: LaidNode[] = [];
  const layers = [...cols.keys()].sort((a, b) => a - b);
  let maxRows = 0;
  for (const l of layers) {
    const group = cols.get(l)!;
    group.sort((a, b) => {
      const bary = (n: ConceptMasteryItem) => {
        const ps = (prereqOf.get(n.conceptId) ?? []).map((p) => yIndex.get(p) ?? 0);
        return ps.length ? ps.reduce((s, v) => s + v, 0) / ps.length : 0;
      };
      return bary(a) - bary(b) || a.name.localeCompare(b.name);
    });
    group.forEach((n, i) => {
      yIndex.set(n.conceptId, i);
      laid.push({
        ...n,
        layer: l,
        x: PAD + l * (NODE_W + COL_GAP),
        y: PAD + i * (NODE_H + ROW_GAP),
      });
    });
    maxRows = Math.max(maxRows, group.length);
  }
  return {
    laid,
    width: PAD * 2 + layers.length * NODE_W + (layers.length - 1) * COL_GAP,
    height: PAD * 2 + maxRows * NODE_H + (maxRows - 1) * ROW_GAP,
  };
}

export function KnowledgeMap({
  courseId,
  concepts,
  edges,
}: {
  courseId: string;
  concepts: ConceptMasteryItem[];
  edges: ConceptEdgeItem[];
}) {
  const navigate = useNavigate();
  // 대표 개념(커리큘럼 절 연결)만 — 전체 개념(수백)을 다 그리면 지도가 아니라 안개
  const nodes = useMemo(() => concepts.filter((c) => c.sectionId), [concepts]);
  const { laid, width, height } = useMemo(() => layoutNodes(nodes, edges), [nodes, edges]);
  const byId = useMemo(() => new Map(laid.map((n) => [n.conceptId, n])), [laid]);

  const drawEdges = useMemo(
    () =>
      edges.filter(
        (e) => byId.has(e.fromConceptId) && byId.has(e.toConceptId),
      ),
    [edges, byId],
  );

  if (nodes.length === 0) return null;

  return (
    <div className="overflow-hidden rounded-2xl border border-border-primary bg-white">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border-primary px-6 py-4">
        <span className="text-[0.9rem] font-bold text-text-secondary">
          지식 지도 — 개념 {nodes.length}개 · 선행 관계 {drawEdges.filter((e) => e.kind === "prerequisite").length}개
        </span>
        <div className="flex items-center gap-3 text-[0.78rem] text-text-tertiary">
          {(Object.keys(STATUS_FILL) as (keyof typeof STATUS_FILL)[]).map((s) => (
            <span key={s} className="inline-flex items-center gap-1.5">
              <span
                className="inline-block h-2.5 w-2.5 rounded-full border"
                style={{ background: STATUS_FILL[s].bg, borderColor: STATUS_FILL[s].border }}
              />
              {{ mastered: "완료", learning: "학습 중", todo: "예정", locked: "잠금" }[s]}
            </span>
          ))}
          <span className="inline-flex items-center gap-1.5">
            <svg width="22" height="8"><line x1="0" y1="4" x2="22" y2="4" stroke="#94a3b8" strokeWidth="1.5" /></svg>
            선행
          </span>
        </div>
      </div>
      <div className="overflow-auto p-2" style={{ maxHeight: 520 }}>
        <svg width={width} height={height} className="block">
          <defs>
            <marker id="km-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
              <path d="M 0 1 L 9 5 L 0 9 z" fill="#94a3b8" />
            </marker>
          </defs>
          {/* 엣지 — 선행(왼쪽) → 학습대상(오른쪽). contains는 옅은 점선 */}
          {drawEdges.map((e, i) => {
            const prereq = byId.get(e.toConceptId)!; // to = 선행
            const target = byId.get(e.fromConceptId)!; // from = 학습대상
            const x1 = prereq.x + NODE_W;
            const y1 = prereq.y + NODE_H / 2;
            const x2 = target.x;
            const y2 = target.y + NODE_H / 2;
            const mx = (x1 + x2) / 2;
            const pre = e.kind === "prerequisite";
            return (
              <path
                key={i}
                d={`M ${x1} ${y1} C ${mx} ${y1}, ${mx} ${y2}, ${x2} ${y2}`}
                fill="none"
                stroke={pre ? "#94a3b8" : "#e2e8f0"}
                strokeWidth={pre ? 1.5 : 1}
                strokeDasharray={pre ? undefined : "4 4"}
                markerEnd={pre ? "url(#km-arrow)" : undefined}
              />
            );
          })}
          {/* 노드 — mastery 색 + 강도 바. 클릭하면 그 절 학습으로 직행 */}
          {laid.map((n) => {
            const st = STATUS_FILL[n.status];
            return (
              <g
                key={n.conceptId}
                transform={`translate(${n.x}, ${n.y})`}
                className="cursor-pointer"
                onClick={() => navigate(`/learning/${courseId}?section=${n.sectionId}`)}
              >
                <title>{`${n.name} — ${Math.round(n.strength * 100)}% (클릭하면 이 절로 이동)`}</title>
                <rect width={NODE_W} height={NODE_H} rx={12} fill={st.bg} stroke={st.border} strokeWidth={1.5} />
                <text x={12} y={20} fontSize={12} fontWeight={700} fill={st.text}>
                  {n.name.length > 13 ? n.name.slice(0, 12) + "…" : n.name}
                </text>
                <rect x={12} y={30} width={NODE_W - 24} height={5} rx={2.5} fill="rgba(0,0,0,0.08)" />
                <rect x={12} y={30} width={(NODE_W - 24) * Math.min(1, n.strength)} height={5} rx={2.5} fill={st.border} />
              </g>
            );
          })}
        </svg>
      </div>
    </div>
  );
}
