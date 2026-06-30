import { CurriculumView } from "@/features/learning/components/CurriculumView";

// 화면 조립 상자 (URL과 1:1). 챕터(개념) 진입 시 JIT 적응형 커리큘럼.
export function CurriculumPage() {
  return (
    <section>
      <h1>JIT 커리큘럼</h1>
      <p style={{ color: "#666" }}>
        진단 점수에 따라 챕터형 이론 설명 + 인출 연습을 생성합니다. 진단 완료 시
        가장 약한 개념으로 자동 이동합니다.
      </p>
      <CurriculumView />
    </section>
  );
}
