import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { Button } from "@/shared/ui/Button";
import { useUploadDocument } from "@/features/documents/queries/useUploadDocument";
import type { CourseDetail } from "@/features/documents/types";
import { useFlowStore } from "@/shared/store/flowStore";
import { apiErrorMessage } from "@/shared/api/errors";

function ConceptGraph({ course }: { course: CourseDetail }) {
  const nameById = useMemo(
    () => new Map(course.concepts.map((c) => [c.id, c.name])),
    [course.concepts],
  );

  return (
    <div>
      <h3>
        추출된 개념 {course.concept_count}개 · 상태: {course.status}
      </h3>
      <ul style={{ listStyle: "none", padding: 0 }}>
        {course.concepts.map((c) => (
          <li
            key={c.id}
            style={{
              marginLeft: c.depth_level * 16,
              padding: "6px 0",
              borderBottom: "1px solid #eee",
            }}
          >
            <strong>{c.name}</strong>{" "}
            <span style={{ color: "#888", fontSize: 12 }}>
              (depth {c.depth_level})
            </span>
            <div style={{ fontSize: 13, color: "#444" }}>{c.description}</div>
            {c.prerequisite_ids.length > 0 && (
              <div style={{ fontSize: 12, color: "#2563eb" }}>
                선수지식:{" "}
                {c.prerequisite_ids.map((id) => nameById.get(id) ?? id).join(", ")}
              </div>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

export function UploadPanel() {
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const { mutate, data, isPending, error } = useUploadDocument();
  const setCourse = useFlowStore((s) => s.setCourse);
  const navigate = useNavigate();

  function handleUpload() {
    if (!file) return;
    mutate(
      { file, title: title || undefined },
      {
        onSuccess: (course) => {
          setCourse(
            course.id,
            course.concepts.map((c) => ({ id: c.id, name: c.name })),
          );
        },
      },
    );
  }

  return (
    <div>
      <input
        type="file"
        accept="application/pdf"
        onChange={(e) => setFile(e.target.files?.[0] ?? null)}
      />
      <input
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        placeholder="제목(선택)"
        style={{ marginLeft: 8 }}
      />
      <Button onClick={handleUpload} disabled={!file || isPending} style={{ marginLeft: 8 }}>
        {isPending ? "섭취 중(파싱·추출)..." : "업로드 & 개념 추출"}
      </Button>

      {error && <p style={{ color: "crimson" }}>실패: {apiErrorMessage(error)}</p>}
      {data && (
        <>
          <div style={{ margin: "12px 0" }}>
            <Button onClick={() => navigate("/lab/diagnostic")}>
              이 코스로 정밀 진단 시작 →
            </Button>
          </div>
          <ConceptGraph course={data} />
        </>
      )}
    </div>
  );
}
