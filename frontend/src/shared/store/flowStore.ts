// 학습 플로우(자료→진단→커리큘럼) 간 ID를 잇는 공용 UI 상태 (Zustand).
// 페이지 이동 시 수동 ID 입력 없이 컨텍스트를 전달한다.
// persist: 새로고침(F5)해도 materialId/sessionId/conceptId가 날아가지 않게 유지.
import { create } from "zustand";
import { persist } from "zustand/middleware";

export interface FlowConcept {
  id: number;
  name: string;
}

interface FlowState {
  materialId: number | null;
  sessionId: number | null;
  conceptId: number | null;
  concepts: FlowConcept[];
  autoGenerateCurriculum: boolean;
  setMaterial: (id: number, concepts: FlowConcept[]) => void;
  setSession: (id: number) => void;
  setConcept: (id: number) => void;
  setAutoGenerateCurriculum: (v: boolean) => void;
  reset: () => void;
}

export const useFlowStore = create<FlowState>()(
  persist(
    (set) => ({
      materialId: null,
      sessionId: null,
      conceptId: null,
      concepts: [],
      autoGenerateCurriculum: false,
      setMaterial: (id, concepts) =>
        set({ materialId: id, concepts, sessionId: null, conceptId: null }),
      setSession: (id) => set({ sessionId: id }),
      setConcept: (id) => set({ conceptId: id }),
      setAutoGenerateCurriculum: (v) => set({ autoGenerateCurriculum: v }),
      reset: () =>
        set({
          materialId: null,
          sessionId: null,
          conceptId: null,
          concepts: [],
          autoGenerateCurriculum: false,
        }),
    }),
    { name: "metalearn-flow" },
  ),
);
