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
  const isPrereq = unit.unit_type === "prerequisite";

  return (
    <li
      style={{
        marginBottom: "0.75rem",
        borderRadius: 8,
        border: `1px solid ${isPrereq ? "#b39ddb" : isWeak ? "#f5c26b" : "#e0e0e0"}`,
        background: isPrereq ? "#faf8ff" : isWeak ? "#fffbf0" : "#fff",
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
            background: isPrereq ? "#7e57c2" : isWeak ? "#f5a623" : "#4a90e2",
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
            <strong style={{ fontSize: "0.95rem", color: isPrereq ? "#4527a0" : isWeak ? "#b05a00" : "#111" }}>
              {unit.title}
            </strong>
            {isPrereq && (
              <span
                style={{
                  fontSize: "0.72rem",
                  background: "#7e57c2",
                  color: "#fff",
                  borderRadius: 4,
                  padding: "1px 6px",
                  fontWeight: 600,
                }}
              >
                사전지식 · 1단계
              </span>
            )}
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
            {!isPrereq && unit.page_numbers.length > 0 && (
              <span style={{ fontSize: "0.78rem", color: "#999" }}>
                p.{unit.page_numbers.join(", ")}
              </span>
            )}
          </div>

          {unit.prereq_reason && (
            <p style={{ margin: "0.25rem 0 0", fontSize: "0.82rem", color: "#5e35b1" }}>
              {unit.prereq_reason}
            </p>
          )}
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
      <h2>3. 나만의 커리큘럼</h2>
      <GenerationBanner mode={curriculum.generation_mode} note={curriculum.generation_note} />

      <p style={{ color: "#555" }}>
        진단 점수 <strong>{Math.round(result.score * 100)}%</strong>
        {slice.learning_goal ? <> · 학습 목표: {goalLabel}</> : null} · 총{" "}
        <strong>{curriculum.total_units}</strong>개 단원 (약점 표시{" "}
        <strong>{curriculum.weakness_count}</strong>개)
        <span style={{ marginLeft: 8, color: "#4a90e2", fontSize: "0.88rem" }}>
          · 사전지식 단원 먼저 → PDF 원문 순서로 학습
        </span>
      </p>

      <p style={{ color: "#666", fontSize: "0.92rem" }}>
        튜터에서 틀리면 더 기초적인 선수 개념으로 내려갈 수 있습니다 (2단계, 3단계…).
      </p>

      <div style={{ marginTop: "1.5rem", display: "flex", flexDirection: "column", gap: "1.5rem" }}>
        {curriculum.chapter_groups.map((group) => (
          <div key={`${group.chapter_id ?? "misc"}-${group.chapter_title}`}>
            <h3
              style={{
                margin: "0 0 0.75rem",
                fontSize: "1rem",
                padding: "0.4rem 0.75rem",
                background: group.chapter_title === "사전 지식" ? "#f3e5f5" : "#f0f4ff",
                borderRadius: 6,
                borderLeft: `4px solid ${group.chapter_title === "사전 지식" ? "#7e57c2" : "#4a90e2"}`,
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
