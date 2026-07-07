import { create } from "zustand";
import type { DraftCourse } from "./types";

// ⚠️ 임시 대역(mock). "코스 생성 → 책장에 생성중 카드 → 완료 전환" 흐름을
//    지금은 setTimeout + 로컬 상태로 흉내낸다.
//
// 백엔드 붙으면 이 스토어는 제거하고 아래로 교체:
//   1) POST /courses 로 서버에 저장(문서·목표 전송) → courses/course_documents/enrollments 생성 + 씨앗 트리거
//   2) /library 에서 React Query 로 GET /courses 리페치 → 새 카드가 "서버에서" 온다
//   3) gen_status='ready' 될 때까지 refetchInterval 폴링 → 카드 '생성중 → 완료'로 전환
//   즉 "서버 저장 + 리페치 + 폴링"을 지금은 이 스토어가 대신할 뿐이다.

const READY_DELAY_MS = 3000; // 생성(씨앗) 완료 흉내 — 백엔드에선 폴링이 이 역할

type State = {
  drafts: DraftCourse[];
  addDraft: (title: string) => string; // 생성중으로 추가 → 잠시 뒤 완료. 생성 id 반환
};

export const useCreatedCourses = create<State>((set) => ({
  drafts: [],
  addDraft: (title) => {
    const id = `draft_${Date.now()}`;
    set((s) => ({ drafts: [{ id, title, generating: true }, ...s.drafts] }));
    setTimeout(() => {
      set((s) => ({
        drafts: s.drafts.map((d) => (d.id === id ? { ...d, generating: false } : d)),
      }));
    }, READY_DELAY_MS);
    return id;
  },
}));
