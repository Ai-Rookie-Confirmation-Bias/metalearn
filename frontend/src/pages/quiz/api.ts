// 문제 페이지 실 API — mock.ts와 같은 함수 모양으로 서버를 부른다.
// 타입은 mock.ts 정의를 그대로 쓴다 (mock이 백엔드 스키마와 1:1로 만들어져 있음).
//
// mock 시절과 달라지는 것:
//   - has_exam_style: 기출 스타일 백엔드(style 컬럼)가 아직 없어 항상 false
//     → [기출 스타일로 풀기] 버튼이 자연히 숨는다 (QUIZ.md §3.6은 백엔드 이후)
//   - studied·last_activity_at: 학습 테이블 집계 전이라 비움 (QUIZ.md §3.5 TODO)
import { apiClient } from "@/shared/api/client";

import type {
  AttemptResponse,
  CourseBank,
  QuizBankSummary,
  SessionItem,
} from "./mock";

type CourseListItem = {
  id: string;
  title: string;
  created_at: string;
  documents: { document_id: string; role: string; seq: number }[];
};

type GenStatus = { status: "idle" | "running" | "done" | "failed" };

// GET /courses + 코스별 quiz 요약 → 과목 선택 화면의 CourseBank 목록.
// 문제은행이 있거나(ready) 지금 생성 중인(generating) 코스만 보여준다 —
// 은행이 아예 없는 코스는 풀 것이 없어 목록에서 뺀다.
export async function fetchCourseBanks(): Promise<CourseBank[]> {
  const { data: courses } = await apiClient.get<CourseListItem[]>("/api/courses");

  const banks = await Promise.all(
    courses.map(async (c): Promise<CourseBank | null> => {
      const { data: summaries } = await apiClient.get<QuizBankSummary[]>(
        `/api/courses/${c.id}/quiz`,
      );
      const summary = summaries[0] ?? null;
      const base = {
        course_id: c.id,
        title: c.title,
        category: `자료 ${c.documents.length}개`,
        last_activity_at: null,
        has_exam_style: false,
      };
      if (summary) return { ...base, status: "ready", summary };

      // 은행이 없다 — 배치가 도는 중이면 "생성 중" 카드로 보여준다
      const docId = c.documents[0]?.document_id;
      if (!docId) return null;
      const { data: gen } = await apiClient.get<GenStatus>(
        `/api/courses/${c.id}/quiz/from-parsing/${docId}/status`,
      );
      if (gen.status === "running") return { ...base, status: "generating", summary: null };
      return null;
    }),
  );
  return banks.filter((b): b is CourseBank => b !== null);
}

// POST /courses/:id/quiz/session — 범위 내 무작위 샘플, 정답 제거되어 도착
export async function fetchSession(
  courseId: string,
  documentId: string,
  tocIndexes: number[],
  count: number,
): Promise<SessionItem[]> {
  const { data } = await apiClient.post<{ items: SessionItem[] }>(
    `/api/courses/${courseId}/quiz/session`,
    { document_id: documentId, toc_indexes: tocIndexes, count },
  );
  return data.items;
}

// POST /quiz/attempts — 서버 채점. 정답·해설·근거 원문이 이때 처음 내려온다
export async function submitAttempt(
  itemId: string,
  userInput: number | boolean | string | string[],
): Promise<AttemptResponse> {
  const { data } = await apiClient.post<AttemptResponse>("/api/quiz/attempts", {
    quiz_item_id: itemId,
    user_input: userInput,
  });
  return data;
}
