import { UploadPanel } from "@/features/materials/components/UploadPanel";

// 화면 조립 상자 (URL과 1:1). 자료 업로드 → 개념 추출 결과 확인.
export function MaterialsPage() {
  return (
    <section>
      <h1>자료 섭취</h1>
      <p style={{ color: "#666" }}>
        PDF를 올리면 Solar Document Parse로 파싱 후 개념·선수지식 그래프로 파편화합니다.
      </p>
      <UploadPanel />
    </section>
  );
}
