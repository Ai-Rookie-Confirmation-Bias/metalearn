import { create } from "zustand";
import { persist } from "zustand/middleware";

import type { Purpose } from "@/features/course-create/types";

// 위저드가 "생성하기"를 눌렀지만 아직 파싱이 안 끝나 코스를 못 만든 상태.
//
// **파싱이 끝나기 전에 POST /courses를 부르면 안 된다.** 역할 제안이 밀도에
// 기대고, 목차 복사는 doc_topics가 생긴 뒤에야 된다. 둘 다 ready 이후에 있다.
// 그래서 의도를 여기 남겨 두고, 책장이 폴링하다 전부 ready가 되면 그때 만든다.
//
// 새로고침을 견뎌야 한다 — 파이프라인이 분 단위다.

export type PendingCourse = {
  // 접수된 파싱 문서 UUID들. 순서 = 위저드에서 올린 순서(메인이 앞).
  documentIds: string[];
  // 책장 카드에 파일명을 보여 줄 때 쓴다. id → filename
  filenames: Record<string, string>;
  title: string;
  purpose: Purpose;
  // 위저드의 자료 유형 최종값. id → textbook|slide|notes|exam.
  // exam은 문제은행 생성에서 빠지고 기출 스타일 프로파일 재료가 된다.
  kinds?: Record<string, string>;
};

type State = {
  pending: PendingCourse | null;
  set: (course: PendingCourse) => void;
  clear: () => void;
};

export const usePendingCourse = create<State>()(
  persist(
    (set) => ({
      pending: null,
      set: (course) => set({ pending: course }),
      clear: () => set({ pending: null }),
    }),
    { name: "metalearn.pending-course" },
  ),
);

/** 위저드 purpose → 진단 goal. 축이 다르다(hobby/culture → interest). */
export function purposeToGoal(purpose: Purpose): "exam" | "work" | "interest" {
  if (purpose === "exam") return "exam";
  if (purpose === "career") return "work";
  return "interest";
}
