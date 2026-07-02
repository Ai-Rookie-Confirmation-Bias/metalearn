import { UploadPanel } from "@/features/documents/components/UploadPanel";

export function DocumentsPage() {
  return (
    <section>
      <h1>문서 섭취</h1>
      <p style={{ color: "#666" }}>
        PDF를 올리면 documents → courses → concepts 순으로 저장됩니다.
      </p>
      <UploadPanel />
    </section>
  );
}
