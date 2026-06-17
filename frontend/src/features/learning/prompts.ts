// 로컬 엔진 구동 시 사용할 해당 도메인 전용 프롬프트 템플릿 (Phase 2)
export const learningPrompts = {
  generate: (topic: string) => `다음 주제로 학습 항목을 만들어줘: ${topic}`,
};
