// [3단계] 순수 UI. JIT 커리큘럼 — 개념별·챕터별 페이지 넘김 + 이론 + 인출.
import { useCallback, useEffect, useRef, useState } from "react";

import { Button } from "@/shared/ui/Button";
import { useFlowStore } from "@/shared/store/flowStore";
import { apiErrorMessage } from "@/shared/api/errors";
import { useCurriculum } from "@/features/learning/queries/useCurriculum";
import type {
  CurriculumBlock,
  CurriculumResponse,
} from "@/features/learning/curriculumTypes";

/** chapter 블록 기준으로 페이지(섹션) 분할. chapter + 뒤따르는 연습을 한 페이지. */
export function groupBlocksIntoPages(blocks: CurriculumBlock[]): CurriculumBlock[][] {
  if (blocks.length === 0) return [];
  const pages: CurriculumBlock[][] = [];
  let page: CurriculumBlock[] = [];
  for (const block of blocks) {
    if (block.kind === "chapter" && page.length > 0) {
      pages.push(page);
      page = [];
    }
    page.push(block);
  }
  if (page.length > 0) pages.push(page);
  return pages;
}

function pageTitle(page: CurriculumBlock[]): string {
  const ch = page.find((b) => b.kind === "chapter");
  if (ch?.title) return ch.title;
  const prose = page.find((b) => b.kind === "prose");
  if (prose?.heading) return prose.heading;
  return "학습 섹션";
}

function CurriculumLoadingPanel({ elapsedSec }: { elapsedSec: number }) {
  let phase = "Solar AI가 챕터 이론과 연습 문제를 생성하고 있습니다.";
  if (elapsedSec >= 120) {
    phase = "거의 완료되었습니다. 잠시만 더 기다려 주세요.";
  } else if (elapsedSec >= 60) {
    phase = "내용이 많아 조금 더 걸리고 있습니다. 정상적으로 진행 중입니다.";
  } else if (elapsedSec >= 20) {
    phase = "진단 점수에 맞춰 맞춤 구성을 설계하는 중입니다.";
  }

  return (
    <div
      role="status"
      aria-live="polite"
      style={{
        marginTop: 24,
        padding: "24px 20px",
        borderRadius: 12,
        border: "2px solid #fbbf24",
        background: "linear-gradient(135deg, #fffbeb 0%, #fef3c7 100%)",
        textAlign: "center",
      }}
    >
      <div
        style={{
          width: 40,
          height: 40,
          margin: "0 auto 16px",
          border: "4px solid #fde68a",
          borderTopColor: "#d97706",
          borderRadius: "50%",
          animation: "curriculum-spin 0.9s linear infinite",
        }}
      />
      <p style={{ margin: "0 0 6px", fontWeight: 700, fontSize: 16, color: "#92400e" }}>
        커리큘럼 생성 중
      </p>
      <p style={{ margin: "0 0 8px", color: "#78350f", fontSize: 14 }}>{phase}</p>
      <p style={{ margin: 0, color: "#a16207", fontSize: 13 }}>
        경과 {elapsedSec}초 · 보통 1~2분 소요 (최대 3분)
      </p>
      <style>{`@keyframes curriculum-spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}

function PagerBar({
  label,
  current,
  total,
  onPrev,
  onNext,
  disabled,
}: {
  label: string;
  current: number;
  total: number;
  onPrev: () => void;
  onNext: () => void;
  disabled?: boolean;
}) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: 12,
        padding: "10px 14px",
        marginBottom: 16,
        borderRadius: 10,
        background: "#f1f5f9",
        border: "1px solid #e2e8f0",
      }}
    >
      <Button onClick={onPrev} disabled={disabled || current <= 0} style={{ minWidth: 72 }}>
        ← 이전
      </Button>
      <div style={{ textAlign: "center", flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 12, color: "#64748b", marginBottom: 2 }}>{label}</div>
        <div style={{ fontWeight: 600, fontSize: 15, color: "#0f172a" }}>
          {current + 1} / {total}
        </div>
      </div>
      <Button
        onClick={onNext}
        disabled={disabled || current >= total - 1}
        style={{ minWidth: 72 }}
      >
        다음 →
      </Button>
    </div>
  );
}

function normalize(s: string): string {
  return s.normalize("NFKC").toLowerCase().replace(/[^0-9a-z가-힣]/g, "");
}

function ChapterBlock({ block }: { block: CurriculumBlock }) {
  return (
    <article
      style={{
        marginBottom: 24,
        padding: "16px 20px",
        borderLeft: "4px solid #2563eb",
        background: "#f8fafc",
        borderRadius: "0 8px 8px 0",
      }}
    >
      <h4 style={{ margin: "0 0 12px", color: "#1e40af", fontSize: 18 }}>{block.title}</h4>
      <div style={{ whiteSpace: "pre-wrap", lineHeight: 1.7, color: "#334155" }}>
        {block.text}
      </div>
    </article>
  );
}

function RetrievalBlock({ block }: { block: CurriculumBlock }) {
  const [value, setValue] = useState("");
  const [revealed, setRevealed] = useState(false);
  const answer = block.answer ?? "";
  const matched = revealed && normalize(value) === normalize(answer);

  return (
    <div
      style={{
        padding: 12,
        border: "1px solid #e5e7eb",
        borderRadius: 8,
        marginBottom: 12,
        background: "#fafafa",
      }}
    >
      <p style={{ fontSize: 12, color: "#7c3aed", margin: 0, fontWeight: 600 }}>
        ✎ 연습 — {block.kind === "cloze" ? "빈칸 인출" : "역질문 인출"}
      </p>
      <p style={{ whiteSpace: "pre-wrap", margin: "6px 0" }}>
        {block.kind === "cloze" ? block.text : block.prompt}
      </p>
      <div style={{ display: "flex", gap: 8 }}>
        <input
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="직접 떠올려 입력"
          style={{ flex: 1, padding: "0.4rem" }}
        />
        <Button onClick={() => setRevealed(true)} disabled={!value.trim()}>
          확인
        </Button>
      </div>
      {revealed && (
        <p
          style={{
            marginTop: 8,
            color: matched ? "#16a34a" : "#b45309",
            fontSize: 14,
          }}
        >
          {matched ? "정답 일치 · " : "정답: "}
          {answer}
        </p>
      )}
    </div>
  );
}

function BlockRenderer({ block }: { block: CurriculumBlock }) {
  if (block.kind === "chapter") return <ChapterBlock block={block} />;
  if (block.kind === "prose") {
    return (
      <div style={{ marginBottom: 12 }}>
        {block.heading && <h4 style={{ margin: "0 0 4px" }}>{block.heading}</h4>}
        <p style={{ whiteSpace: "pre-wrap", margin: 0 }}>{block.text}</p>
      </div>
    );
  }
  return <RetrievalBlock block={block} />;
}

function CurriculumHeader({ c }: { c: CurriculumResponse }) {
  const focused = c.mode === "focused";
  return (
    <div style={{ marginBottom: 16 }}>
      <h3 style={{ margin: "0 0 4px" }}>{c.concept_name}</h3>
      <p style={{ margin: 0, color: "#666", fontSize: 14 }}>
        점수 {Math.round(c.score * 100)}% ·{" "}
        <span style={{ color: focused ? "#16a34a" : "#2563eb", fontWeight: 600 }}>
          {focused
            ? "집중 모드 (메인 100%)"
            : `브릿지 모드 (선수 ${Math.round(c.prerequisite_ratio * 100)}% + 메인 ${Math.round(
                c.main_ratio * 100,
              )}%)`}
        </span>
      </p>
      {!focused && c.prerequisite_names.length > 0 && (
        <p style={{ margin: "4px 0 0", fontSize: 13, color: "#2563eb" }}>
          보강 선수개념: {c.prerequisite_names.join(", ")}
        </p>
      )}
    </div>
  );
}

export function CurriculumView() {
  const flowConcepts = useFlowStore((s) => s.concepts);
  const flowConceptId = useFlowStore((s) => s.conceptId);
  const flowSessionId = useFlowStore((s) => s.sessionId);
  const setFlowConcept = useFlowStore((s) => s.setConcept);
  const autoGenerate = useFlowStore((s) => s.autoGenerateCurriculum);
  const setAutoGenerate = useFlowStore((s) => s.setAutoGenerateCurriculum);

  const hasConceptList = flowConcepts.length > 0;

  const [conceptIdx, setConceptIdx] = useState(() => {
    if (!flowConceptId || flowConcepts.length === 0) return 0;
    const i = flowConcepts.findIndex((c) => c.id === flowConceptId);
    return i >= 0 ? i : 0;
  });
  const [sectionIdx, setSectionIdx] = useState(0);
  const [cache, setCache] = useState<Record<number, CurriculumResponse>>({});
  const [loadingConceptId, setLoadingConceptId] = useState<number | null>(null);
  const [elapsedSec, setElapsedSec] = useState(0);

  const [manualConceptId, setManualConceptId] = useState(
    flowConceptId ? String(flowConceptId) : "",
  );
  const [sessionId, setSessionId] = useState(
    flowSessionId ? String(flowSessionId) : "",
  );

  const { mutate, error, isPending } = useCurriculum();
  const autoTriggered = useRef(false);

  const activeConcept = hasConceptList ? flowConcepts[conceptIdx] : null;
  const activeConceptId =
    activeConcept?.id ?? (manualConceptId ? Number(manualConceptId) : null);
  const displayData = activeConceptId ? cache[activeConceptId] : undefined;
  const isLoadingCurrent =
    isPending && loadingConceptId === activeConceptId;

  const sectionPages = displayData ? groupBlocksIntoPages(displayData.blocks) : [];
  const safeSectionIdx = Math.min(sectionIdx, Math.max(0, sectionPages.length - 1));
  const currentPage = sectionPages[safeSectionIdx] ?? [];

  const sid = sessionId ? Number(sessionId) : flowSessionId ?? undefined;

  const fetchCurriculum = useCallback(
    (conceptId: number, force = false) => {
      setLoadingConceptId(conceptId);
      setElapsedSec(0);
      mutate(
        { conceptId, sessionId: sid, forceRegenerate: force },
        {
          onSuccess: (d) => {
            setCache((prev) => ({ ...prev, [conceptId]: d }));
            setLoadingConceptId((cur) => (cur === conceptId ? null : cur));
          },
          onError: () =>
            setLoadingConceptId((cur) => (cur === conceptId ? null : cur)),
        },
      );
    },
    [mutate, sid],
  );

  // 활성 개념 변경 시 캐시 없으면 로드
  useEffect(() => {
    if (!activeConceptId || cache[activeConceptId]) return;
    if (loadingConceptId === activeConceptId) return;
    fetchCurriculum(activeConceptId);
  }, [activeConceptId, cache, loadingConceptId, fetchCurriculum]);

  // 섹션 인덱스는 개념/데이터 바뀔 때 리셋
  useEffect(() => {
    setSectionIdx(0);
  }, [activeConceptId]);

  // 경과 시간
  useEffect(() => {
    if (!isLoadingCurrent) return;
    setElapsedSec(0);
    const id = window.setInterval(() => setElapsedSec((s) => s + 1), 1000);
    return () => window.clearInterval(id);
  }, [isLoadingCurrent]);

  // 진단 완료 후 자동 생성
  useEffect(() => {
    if (!autoGenerate || autoTriggered.current) return;
    autoTriggered.current = true;
    setAutoGenerate(false);

    if (flowConceptId && flowConcepts.length > 0) {
      const i = flowConcepts.findIndex((c) => c.id === flowConceptId);
      setConceptIdx(i >= 0 ? i : 0);
      fetchCurriculum(flowConceptId);
    } else if (flowConceptId) {
      setManualConceptId(String(flowConceptId));
      fetchCurriculum(flowConceptId);
    }
  }, [
    autoGenerate,
    flowConceptId,
    flowConcepts,
    fetchCurriculum,
    setAutoGenerate,
  ]);

  function goConcept(delta: number) {
    if (!hasConceptList) return;
    const next = Math.max(0, Math.min(flowConcepts.length - 1, conceptIdx + delta));
    if (next === conceptIdx) return;
    setConceptIdx(next);
    setFlowConcept(flowConcepts[next].id);
    setSectionIdx(0);
  }

  function goSection(delta: number) {
    setSectionIdx((i) =>
      Math.max(0, Math.min(sectionPages.length - 1, i + delta)),
    );
  }

  function handleManualGenerate() {
    const cid = Number(manualConceptId);
    if (!cid) return;
    setCache({});
    fetchCurriculum(cid, true);
  }

  return (
    <div>
      {!hasConceptList && (
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 12 }}>
          <input
            value={manualConceptId}
            onChange={(e) => setManualConceptId(e.target.value)}
            placeholder="개념 ID (Concept #)"
            inputMode="numeric"
          />
          <input
            value={sessionId}
            onChange={(e) => setSessionId(e.target.value)}
            placeholder="진단 세션 ID (선택)"
            inputMode="numeric"
          />
          <Button
            onClick={handleManualGenerate}
            disabled={!manualConceptId || isLoadingCurrent}
          >
            {isLoadingCurrent ? "생성 중..." : "커리큘럼 생성"}
          </Button>
        </div>
      )}

      {hasConceptList && (
        <PagerBar
          label={`개념 · ${activeConcept?.name ?? ""}`}
          current={conceptIdx}
          total={flowConcepts.length}
          onPrev={() => goConcept(-1)}
          onNext={() => goConcept(1)}
          disabled={isLoadingCurrent}
        />
      )}

      {isLoadingCurrent && <CurriculumLoadingPanel elapsedSec={elapsedSec} />}

      {error && loadingConceptId === activeConceptId && (
        <div style={{ marginTop: 16, padding: 12, borderRadius: 8, background: "#fef2f2" }}>
          <p style={{ color: "crimson", margin: 0 }}>생성 실패: {apiErrorMessage(error)}</p>
        </div>
      )}

      {displayData && !isLoadingCurrent && (
        <div style={{ marginTop: 8 }}>
          <CurriculumHeader c={displayData} />

          {sectionPages.length > 1 && (
            <PagerBar
              label={pageTitle(currentPage)}
              current={safeSectionIdx}
              total={sectionPages.length}
              onPrev={() => goSection(-1)}
              onNext={() => goSection(1)}
            />
          )}

          {currentPage.map((block, idx) => (
            <BlockRenderer key={`${safeSectionIdx}-${idx}`} block={block} />
          ))}

          {sectionPages.length > 1 && (
            <div style={{ display: "flex", justifyContent: "center", marginTop: 8 }}>
              <Button
                onClick={() => goSection(1)}
                disabled={safeSectionIdx >= sectionPages.length - 1}
              >
                다음 섹션 →
              </Button>
            </div>
          )}
        </div>
      )}

      {hasConceptList && !displayData && !isLoadingCurrent && !error && (
        <p style={{ color: "#666", marginTop: 16 }}>
          「{activeConcept?.name}」 커리큘럼을 불러오는 중입니다...
        </p>
      )}
    </div>
  );
}
