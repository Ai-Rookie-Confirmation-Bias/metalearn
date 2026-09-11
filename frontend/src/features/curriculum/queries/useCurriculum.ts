// [2단계] TanStack Query 훅.
//
// 답을 기록하면 자료·목차 캐시를 통째로 무효화한다. 한 절의 결과가 목차 분량과
// 문서 준비도까지 바꾸기 때문에 부분 갱신으로는 화면이 어긋난다 —
// "학습 → 분석 → 커리큘럼 변경"이 눈에 보이는 게 이 화면의 목적이다.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { AttemptKind } from "@/features/curriculum/api/curriculum";
import {
  fetchChapter,
  fetchDocument,
  fetchDocuments,
  fetchFormative,
  fetchLesson,
  fetchReview,
  submitAnswer,
} from "@/features/curriculum/api/curriculum";

export const curriculumKeys = {
  documents: ["curriculum", "documents"] as const,
  document: (docId: string) => ["curriculum", "document", docId] as const,
  chapter: (docId: string, index: number) =>
    ["curriculum", "chapter", docId, index] as const,
  lesson: (docId: string, sectionId: string) =>
    ["curriculum", "lesson", docId, sectionId] as const,
  formative: (docId: string, index: number) =>
    ["curriculum", "formative", docId, index] as const,
  // days는 시연용 시계 이동. 시점마다 다른 목록이라 키에 들어가야 한다.
  review: (docId: string, days: number) =>
    ["curriculum", "review", docId, days] as const,
};

export function useDocuments() {
  return useQuery({ queryKey: curriculumKeys.documents, queryFn: fetchDocuments });
}

export function useDocument(docId: string | undefined) {
  return useQuery({
    queryKey: curriculumKeys.document(docId ?? ""),
    queryFn: () => fetchDocument(docId as string),
    enabled: Boolean(docId),
  });
}

export function useChapter(docId: string | undefined, index: number | undefined) {
  return useQuery({
    queryKey: curriculumKeys.chapter(docId ?? "", index ?? -1),
    queryFn: () => fetchChapter(docId as string, index as number),
    enabled: Boolean(docId) && index !== undefined,
  });
}

/** 절 하나의 학습 콘텐츠. 첫 생성이 5~10초라 오래 들고 있는다. */
export function useLesson(docId: string | undefined, sectionId: string | undefined) {
  return useQuery({
    queryKey: curriculumKeys.lesson(docId ?? "", sectionId ?? ""),
    queryFn: () => fetchLesson(docId as string, sectionId as string),
    enabled: Boolean(docId && sectionId),
    staleTime: Infinity, // 같은 절을 다시 열었을 때 다른 글이 나오면 안 된다
  });
}

/** 단원 평가. 잠겨 있으면 blocks가 비고 reason이 얼마나 더 해야 하는지 말한다. */
export function useFormative(docId: string | undefined, index: number | undefined) {
  return useQuery({
    queryKey: curriculumKeys.formative(docId ?? "", index ?? -1),
    queryFn: () => fetchFormative(docId as string, index as number),
    enabled: Boolean(docId) && index !== undefined,
    // 풀고 있는 도중에 문항이 바뀌면 안 된다.
    staleTime: Infinity,
  });
}

export function useAnswer(docId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (args: {
      sectionId: string;
      correct: boolean;
      conceptKey?: string;
      kind?: AttemptKind;
    }) => submitAnswer({ docId, ...args }),
    onSuccess: () => {
      // 화면 하나의 결과가 목차 분량과 문서 준비도까지 바꾼다. 다만 lesson과
      // formative는 다시 안 부른다 — 방금 읽은 설명이나 풀고 있는 문항이
      // 답을 맞혔다고 바뀌면 안 된다.
      qc.invalidateQueries({ queryKey: ["curriculum", "document"] });
      qc.invalidateQueries({ queryKey: ["curriculum", "chapter"] });
    },
  });
}

/** 복습 큐. 화면마다 문항을 만들므로 첫 호출이 느리다(화면당 1콜). */
export function useReview(docId: string | undefined, days: number) {
  return useQuery({
    queryKey: curriculumKeys.review(docId ?? "", days),
    queryFn: () => fetchReview(docId as string, days),
    enabled: Boolean(docId),
    // 풀고 있는 도중에 문항이 바뀌면 안 된다.
    staleTime: Infinity,
  });
}
