import { useState } from "react";

import { TutorSession } from "@/features/learning/components/TutorSession";
import { GenerationBanner } from "@/features/seed/components/GenerationBanner";
import type { Curriculum, CurriculumUnit, DiagnosticResult, SeedSlice } from "@/features/seed/types";
import { LEARNING_GOAL_LABELS, type LearningGoal } from "@/features/seed/types";
import { Button } from "@/shared/ui/Button";

interface Props {
  result: DiagnosticResult;
  slice: SeedSlice;
  curriculum: Curriculum;
  onReset: () => void;
}

function UnitCard({ unit, profileId }: { unit: CurriculumUnit; profileId: string }) {
  const [tutorActive, setTutorActive] = useState(false);
  const isWeak = unit.priority === "weakness";

  return (
    <li
      style={{
        marginBottom: "0.75rem",
        borderRadius: 8,
        border: `1px solid ${isWeak ? "#f5c26b" : "#e0e0e0"}`,
        background: isWeak ? "#fffbf0" : "#fff",
        overflow: "hidden",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "flex-start",
          gap: "0.5rem",
          padding: "0.75rem 1rem",
        }}
      >
        <span
          style={{
            minWidth: 28,
            height: 28,
            borderRadius: "50%",
            background: isWeak ? "#f5a623" : "#4a90e2",
            color: "#fff",
            fontSize: "0.78rem",
            fontWeight: 700,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            flexShrink: 0,
          }}
        >
          {unit.order}
        </span>

        <div style={{ flex: 1 }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", flexWrap: "wrap" }}>
            <strong style={{ fontSize: "0.95rem", color: isWeak ? "#b05a00" : "#111" }}>
              {unit.title}
            </strong>
            {isWeak && (
              <span
                style={{
                  fontSize: "0.72rem",
                  background: "#f5a623",
                  color: "#fff",
                  borderRadius: 4,
                  padding: "1px 6px",
                  fontWeight: 600,
                }}
              >
                약점 · 보강
              </span>
            )}
            <span style={{ fontSize: "0.78rem", color: "#999" }}>
              p.{unit.page_numbers.join(", ")}
            </span>
          </div>

          {unit.summary && (
            <p style={{ margin: "0.25rem 0 0", fontSize: "0.82rem", color: "#555" }}>
              {unit.summary}
            </p>
          )}
          {unit.focus && (
            <p style={{ margin: "0.2rem 0 0", fontSize: "0.8rem", color: "#4a90e2" }}>
              → {unit.focus}
            </p>
          )}

          {!tutorActive && (
            <Button
              style={{ marginTop: "0.65rem", fontSize: "0.85rem" }}
              onClick={() => setTutorActive(true)}
            >
              학습 시작
            </Button>
          )}
        </div>
      </div>

      {tutorActive && (
        <TutorSession
          profileId={profileId}
          unit={unit}
          onComplete={() => setTutorActive(false)}
        />
      )}
    </li>
  );
}

export function CurriculumView({ result, slice, curriculum, onReset }: Props) {
  const goalLabel =
    slice.learning_goal && slice.learning_goal in LEARNING_GOAL_LABELS
      ? LEARNING_GOAL_LABELS[slice.learning_goal as LearningGoal]
      : slice.learning_goal ?? "—";

  return (
    <section>
      <h2>5. 나만의 커리큘럼</h2>
      <GenerationBanner mode={curriculum.generation_mode} note={curriculum.generation_note} />

      <p style={{ color: "#555" }}>
        진단 점수 <strong>{Math.round(result.score * 100)}%</strong> · 학습 목표: {goalLabel} · 총{" "}
        <strong>{curriculum.total_units}</strong>개 단원 (약점 우선{" "}
        <strong>{curriculum.weakness_count}</strong>개)
        <span style={{ marginLeft: 8, color: "#4a90e2", fontSize: "0.88rem" }}>
          · 단원별 <strong>학습 시작</strong> → 설명 학습 → 확인 문제 순으로 진행하세요
        </span>
      </p>

      {curriculum.weakness_count > 0 && (
        <p style={{ color: "#a40", fontSize: "0.95rem" }}>
          약점 개념을 먼저 학습한 뒤, 나머지 범위를 이어갑니다.
        </p>
      )}

      <div style={{ marginTop: "1.5rem", display: "flex", flexDirection: "column", gap: "1.5rem" }}>
        {curriculum.chapter_groups.map((group) => (
          <div key={`${group.chapter_id ?? "misc"}-${group.chapter_title}`}>
            <h3
              style={{
                margin: "0 0 0.75rem",
                fontSize: "1rem",
                padding: "0.4rem 0.75rem",
                background: "#f0f4ff",
                borderRadius: 6,
                borderLeft: "4px solid #4a90e2",
              }}
            >
              {group.chapter_title}
            </h3>
            <ol style={{ margin: 0, padding: 0, listStyle: "none" }}>
              {group.units.map((unit) => (
                <UnitCard key={unit.concept_id} unit={unit} profileId={slice.profile_id} />
              ))}
            </ol>
          </div>
        ))}
      </div>

      <details style={{ marginTop: "1.5rem" }}>
        <summary style={{ cursor: "pointer", color: "#666" }}>Seed 슬라이스 JSON</summary>
        <pre
          style={{
            background: "#f6f6f6",
            padding: "1rem",
            borderRadius: 8,
            overflow: "auto",
            fontSize: "0.85rem",
            marginTop: "0.5rem",
          }}
        >
          {JSON.stringify(slice, null, 2)}
        </pre>
      </details>

      <Button onClick={onReset} style={{ marginTop: "1.5rem" }}>
        처음부터 다시
      </Button>
    </section>
  );
}
