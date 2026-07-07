// 학습 플로우(문서→코스→진단→커리큘럼) 간 ID를 잇는 공용 UI 상태.
import { create } from "zustand";
import { persist } from "zustand/middleware";

export interface FlowConcept {
  id: number;
  name: string;
}

interface FlowState {
  courseId: number | null;
  sessionId: number | null;
  conceptId: number | null;
  concepts: FlowConcept[];
  autoGenerateCurriculum: boolean;
  setCourse: (id: number, concepts: FlowConcept[]) => void;
  setSession: (id: number) => void;
  setConcept: (id: number) => void;
  setAutoGenerateCurriculum: (v: boolean) => void;
  reset: () => void;
}

export const useFlowStore = create<FlowState>()(
  persist(
    (set) => ({
      courseId: null,
      sessionId: null,
      conceptId: null,
      concepts: [],
      autoGenerateCurriculum: false,
      setCourse: (id, concepts) =>
        set({ courseId: id, concepts, sessionId: null, conceptId: null }),
      setSession: (id) => set({ sessionId: id }),
      setConcept: (id) => set({ conceptId: id }),
      setAutoGenerateCurriculum: (v) => set({ autoGenerateCurriculum: v }),
      reset: () =>
        set({
          courseId: null,
          sessionId: null,
          conceptId: null,
          concepts: [],
          autoGenerateCurriculum: false,
        }),
    }),
    { name: "metalearn-flow" },
  ),
);
