// [2단계] TanStack Query 훅.
//
// 답을 기록하면 자료·목차 캐시를 통째로 무효화한다. 한 절의 결과가 목차 분량과
// 문서 준비도까지 바꾸기 때문에 부분 갱신으로는 화면이 어긋난다 —
// "학습 → 분석 → 커리큘럼 변경"이 눈에 보이는 게 이 화면의 목적이다.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  fetchChapter,
  fetchDocument,
  fetchDocuments,
  fetchLesson,
  submitAnswer,
} from "@/features/curriculum/api/curriculum";

export const curriculumKeys = {
  documents: ["curriculum", "documents"] as const,
  document: (docId: string) => ["curriculum", "document", docId] as const,
  chapter: (docId: string, index: number) =>
    ["curriculum", "chapter", docId, index] as const,
  lesson: (docId: string, sectionId: string) =>
    ["curriculum", "lesson", docId, sectionId] as const,
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

export function useAnswer(docId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (args: { sectionId: string; correct: boolean; conceptKey?: string }) =>
      submitAnswer({ docId, ...args }),
    onSuccess: () => {
      // 절 하나의 결과가 목차 분량과 문서 준비도까지 바꾼다. 다만 lesson은
      // 다시 안 부른다 — 방금 읽은 설명이 답을 맞혔다고 바뀌면 안 된다.
      qc.invalidateQueries({ queryKey: ["curriculum", "document"] });
      qc.invalidateQueries({ queryKey: ["curriculum", "chapter"] });
    },
  });
}
