import { useRef, useState } from "react";

import { Button } from "@/shared/ui/Button";

interface Props {
  onUpload: (file: File) => void;
  isPending: boolean;
  error: string | null;
}

export function PdfUploadStep({ onUpload, isPending, error }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [selected, setSelected] = useState<File | null>(null);

  return (
    <section>
      <h2>1. PDF 업로드</h2>
      <p style={{ color: "#555", marginBottom: "1rem" }}>
        학습할 PDF를 업로드하면 Upstage Document Parse로 목차·개념 skeleton을 생성합니다.
      </p>
      <input
        ref={inputRef}
        type="file"
        accept="application/pdf,.pdf"
        onChange={(e) => setSelected(e.target.files?.[0] ?? null)}
      />
      <div style={{ marginTop: "1rem" }}>
        <Button
          disabled={!selected || isPending}
          onClick={() => selected && onUpload(selected)}
        >
          {isPending ? "AI 파싱 중…" : "업로드"}
        </Button>
      </div>
      {selected && (
        <p style={{ marginTop: "0.5rem", fontSize: "0.9rem" }}>선택: {selected.name}</p>
      )}
      {error && <p style={{ color: "crimson", marginTop: "0.75rem" }}>{error}</p>}
    </section>
  );
}
