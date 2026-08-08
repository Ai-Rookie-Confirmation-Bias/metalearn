import { create } from "zustand";
import { persist } from "zustand/middleware";

import type { Purpose } from "@/features/course-create/types";
import type { Goal } from "@/features/course/api";

/** 위저드에서 고른 수업 하나. **아직 서버에 없다.**
 *
 * 코스는 자료가 전부 `ready`가 된 다음에야 만들 수 있어서(서버가 그 자리에서
 * 목차를 복사한다), 위저드가 끝나도 바로 못 만든다. 파싱이 분 단위라 그 사이에
 * 창을 닫는 일이 실제로 일어나므로 이 초안은 **새로고침을 견뎌야 한다.**
 */
export type CourseDraft = {
  /** 화면 안에서만 쓰는 id. */
  id: string;
  title: string;
  docIds: string[];
  purpose: Purpose;
  /** POST /courses가 성공하면 채워진다. 이후로는 이 초안이 코스를 가리킨다. */
  courseId?: string;
  /** 진단까지 끝냈나. 책장이 "진단 시작하기"를 언제 감출지 고르는 값. */
  diagnosed?: boolean;
};

type State = {
  drafts: CourseDraft[];
  add: (draft: CourseDraft) => void;
  patch: (id: string, changes: Partial<CourseDraft>) => void;
  remove: (id: string) => void;
};

export const useCourseDrafts = create<State>()(
  persist(
    (set) => ({
      drafts: [],
      add: (draft) => set((s) => ({ drafts: [draft, ...s.drafts] })),
      patch: (id, changes) =>
        set((s) => ({
          drafts: s.drafts.map((d) => (d.id === id ? { ...d, ...changes } : d)),
        })),
      remove: (id) => set((s) => ({ drafts: s.drafts.filter((d) => d.id !== id) })),
    }),
    { name: "metalearn.course-drafts" },
  ),
);

/** 위저드의 목표 → 서버의 `goal`.
 *
 * 화면은 넷(시험·실무·교양·취미)이고 서버는 셋(exam·work·interest)이다.
 * 서버가 이 값으로 정하는 건 **분량**이라, 교양과 취미를 가르는 값이 없다.
 */
export function toGoal(purpose: Purpose): Goal {
  if (purpose === "exam") return "exam";
  if (purpose === "career") return "work";
  return "interest";
}

const USER_KEY = "metalearn.user-id";

/** 이 브라우저의 사용자 id.
 *
 * ⚠️ **auth가 없어서 클라이언트가 만든다.** `POST /courses`가 `user_id`를 바디로
 * 받는 것도 같은 이유다(백엔드 주석: "users 테이블이 아직 없어 클라이언트가 직접
 * 준다. auth가 들어오면 토큰에서"). 토큰이 붙으면 이 함수와 그 필드가 같이 없어진다.
 */
export function userId(): string {
  const saved = localStorage.getItem(USER_KEY);
  if (saved) return saved;
  const fresh = crypto.randomUUID();
  localStorage.setItem(USER_KEY, fresh);
  return fresh;
}
