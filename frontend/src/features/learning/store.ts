// 클라이언트 UI 전역 상태 (Zustand) — 예: 선택된 탭
import { create } from "zustand";

interface LearningState {
  activeTab: string;
  setActiveTab: (tab: string) => void;
}

export const useLearningStore = create<LearningState>((set) => ({
  activeTab: "tutor",
  setActiveTab: (tab) => set({ activeTab: tab }),
}));
