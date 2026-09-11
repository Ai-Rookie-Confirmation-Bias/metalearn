// 메타인지 분석 — 자료를 가로지른 누적 요약.
//
// 계산은 전부 백엔드(`mastery.py`)가 한다. 여기서 평균을 내거나 등급을 매기지
// 않는다 — 화면이 제 나름대로 계산하기 시작하면 "왜 이 숫자인지"를 두 곳에서
// 찾아야 한다.
import { apiClient } from "@/shared/api/client";

import type { AttemptKind } from "@/features/curriculum/api/curriculum";

export interface AnalysisDoc {
  docId: string;
  title: string;
  readiness: number;
  understanding: number;
  sectionsTotal: number;
  sectionsDone: number;
  sectionsDue: number;
  weakestChapter: string | null;
  weakConcepts: string[];
  byKind: Partial<Record<AttemptKind, number>>;
  insertedChapters: number;
}

export interface AnalysisOut {
  readiness: number;
  understanding: number;
  sectionsTotal: number;
  sectionsDone: number;
  sectionsDue: number;
  attemptsTotal: number;
  // 비어 있는 출처가 곧 빈 구멍이다 — 화면이 그걸 숨기지 않는다.
  byKind: Partial<Record<AttemptKind, number>>;
  documents: AnalysisDoc[];
  // [개념, 몇 개 목차에서 약점으로 잡혔나]
  weakConcepts: [string, number][];
  // ✚ 진단이 목차 앞에 끼운 보강 단원 수.
  // 진단은 문항 점수를 쌓지 않는다 — 배울 순서를 바꾼다. 그게 여기 숫자다.
  insertedChapters: number;
}

export async function fetchAnalysis(): Promise<AnalysisOut> {
  const { data } = await apiClient.get<AnalysisOut>("/api/curriculum/analysis", {
    timeout: 120000,
  });
  return data;
}
