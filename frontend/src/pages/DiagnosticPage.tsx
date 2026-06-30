import { DiagnosticPanel } from "@/features/diagnostic/components/DiagnosticPanel";

// 화면 조립 상자 (URL과 1:1). BKT 기반 무제한 정밀 진단.
export function DiagnosticPage() {
  return (
    <section>
      <h1>정밀 진단</h1>
      <p style={{ color: "#666" }}>
        가장 불확실한 개념을 타겟팅해 출제하고, 신뢰도가 앎/모름으로 확정될 때까지 반복합니다.
      </p>
      <DiagnosticPanel />
    </section>
  );
}
