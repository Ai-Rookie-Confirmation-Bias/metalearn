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

type GenStatus = {
  status: "idle" | "running" | "done" | "failed";
  saved: number; // done일 때 이번 실행이 추가·저장한 문항 수 (0 = 빈손)
};

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

      // 생성 배치 상태 — 은행이 없으면 "생성 중" 카드의 근거, 은행이 있으면
      // 리필(새 문제 추가)이 도는 중이라는 표시(refilling)의 근거가 된다.
      const docId = summary?.document_id ?? c.documents[0]?.document_id;
      if (!docId) return null;
      const { data: gen } = await apiClient.get<GenStatus>(
        `/api/courses/${c.id}/quiz/from-parsing/${docId}/status`,
      );
      const running = gen.status === "running";

      if (summary) return { ...base, status: "ready", summary, refilling: running };
      if (running) return { ...base, status: "generating", summary: null };
      return null;
    }),
  );
  return banks.filter((b): b is CourseBank => b !== null);
}

// 세션 응답 — 안 푼 문항 우선 샘플. recycled = 안 푼 게 모자라 복습으로
// 다시 나온 문항 수 (items의 뒤쪽 recycled개가 복습분).
export type SessionData = { items: SessionItem[]; recycled: number };

// POST /courses/:id/quiz/session — 범위 내 무작위 샘플, 정답 제거되어 도착.
// excludeIds(푼 지 오래된 순)를 보내면 안 푼 문항을 먼저 주고, 모자라면
// 오래 전에 푼 것부터 복습으로 채워 준다.
export async function fetchSession(
  courseId: string,
  documentId: string,
  tocIndexes: number[],
  count: number,
  excludeIds: string[] = [],
): Promise<SessionData> {
  const { data } = await apiClient.post<SessionData>(
    `/api/courses/${courseId}/quiz/session`,
    {
      document_id: documentId,
      toc_indexes: tocIndexes,
      count,
      exclude_ids: excludeIds,
    },
  );
  return data;
}

// GET …/from-parsing/:docId/status — 생성 작업 결과 조회.
// 리필 완료 순간 saved를 읽어 "N개 추가됐어요 / 못 만들었어요"를 가르는 데 쓴다.
export async function fetchGenStatus(
  courseId: string,
  documentId: string,
): Promise<GenStatus> {
  const { data } = await apiClient.get<GenStatus>(
    `/api/courses/${courseId}/quiz/from-parsing/${documentId}/status`,
  );
  return data;
}

// POST …/from-parsing/:docId?mode=append — 리필 접수 (202).
// 생성은 분 단위 작업이라 완료를 기다리지 않는다 — 끝나면 은행 문항 수에
// 자동 반영되고, 기존 문항은 유지된 채 새 문항만 추가된다.
// 이미 생성 중이면 서버가 409를 준다 (호출부에서 조용히 무시해도 되는 상태).
export async function requestRefill(
  courseId: string,
  documentId: string,
): Promise<void> {
  await apiClient.post(
    `/api/courses/${courseId}/quiz/from-parsing/${documentId}?mode=append`,
  );
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
