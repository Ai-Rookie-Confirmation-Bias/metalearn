import { TutorPanel } from "@/features/learning/components/TutorPanel";

// 화면 조립 상자 (URL과 1:1). features의 컴포넌트를 가져와 레이아웃만 구성.
export function LearningPage() {
  return (
    <section>
      <h1>학습</h1>
      <TutorPanel />
    </section>
  );
}
