import { create } from "zustand";
import { persist } from "zustand/middleware";

// 방금 올려서 아직 파싱이 안 끝난 자료들.
//
// **여기에 진행 상태는 없다.** 상태는 서버가 갖고 React Query가 폴링한다
// (아키텍처 원칙 3). 이 스토어가 들고 있는 건 "책장이 아직 모르는 문서 id"뿐이다 —
// 커리큘럼 목록(`GET /api/curriculum/documents`)은 ready인 문서만 주므로,
// 파싱이 끝나기 전까지는 이 목록이 그 자료를 가리키는 유일한 단서다.
//
// 새로고침을 견뎌야 한다. 파이프라인이 분 단위라 그 사이에 창을 닫는 일이
// 실제로 일어나고, 그러면 올린 자료가 책장에서 통째로 사라져 보인다.

export type PendingUpload = {
  docId: string; // 파싱 UUID. 책장 링크 `/curriculum/{id}`가 이 값으로 열린다
  filename: string;
};

type State = {
  pending: PendingUpload[];
  add: (items: PendingUpload[]) => void;
  remove: (docId: string) => void;
};

export const usePendingUploads = create<State>()(
  persist(
    (set) => ({
      pending: [],
      add: (items) =>
        set((s) => {
          // 같은 파일을 다시 올리면 서버가 같은 id를 돌려준다(지문 재사용).
          const fresh = items.filter(
            (item) => !s.pending.some((p) => p.docId === item.docId),
          );
          return { pending: [...fresh, ...s.pending] };
        }),
      remove: (docId) =>
        set((s) => ({ pending: s.pending.filter((p) => p.docId !== docId) })),
    }),
    { name: "metalearn.pending-uploads" },
  ),
);
