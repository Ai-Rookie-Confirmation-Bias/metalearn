// [1단계] 커리큘럼 백엔드 호출.
//
// 판단은 전부 백엔드에서 끝나 있다. 여기서 계산하거나 문구를 만들지 않는다 —
// reason은 규칙이 만든 문장이라 그대로 화면에 나가야 "왜 이렇게 나왔는지"가
// 검증 가능한 상태로 유지된다.
import { apiClient } from "@/shared/api/client";

export type MasteryStatus = "untouched" | "learning" | "weak" | "shaky" | "solid";
export type PlanMode = "deep" | "normal" | "compressed";

export interface ChapterBrief {
  index: number;
  title: string;
  pages: string;
  sectionsTotal: number;
  sectionsDone: number;
  status: MasteryStatus;
  statusLabel: string;
  ratio: number; // 이해도 — 시도한 절만으로
  progress: number; // 진도 — 얼마나 훑었나
  mode: PlanMode;
  reason: string; // ⚡ 비어 있으면 아직 판단 근거가 없다는 뜻
}

export interface DocumentOut {
  docId: string;
  title: string;
  readiness: number;
  complete: boolean;
  sectionsTotal: number;
  remainingSections: number;
  estimatedMinutes: number;
  weakestChapter: number | null;
  chapters: ChapterBrief[];
}

export interface SectionOut {
  sectionId: string;
  order: number;
  title: string;
  concepts: string[];
  reason: string; // ⚡ 왜 이 개념들이 한 화면에 묶였는지
  page: string;
  status: MasteryStatus;
  statusLabel: string;
  attempts: number;
  improving: boolean;
  weakConcepts: string[];
}

export interface ChapterOut {
  docId: string;
  docTitle: string;
  index: number;
  title: string;
  pages: string;
  readiness: number;
  ratio: number;
  progress: number;
  mode: PlanMode;
  reason: string;
  weakConcepts: string[];
  sections: SectionOut[];
}

export interface AnswerOut {
  sectionId: string;
  status: MasteryStatus;
  statusLabel: string;
  attempts: number;
  improving: boolean;
  chapterRatio: number;
  chapterMode: PlanMode;
  chapterReason: string;
  readiness: number;
}

const base = "/api/curriculum";

export async function fetchDocuments(): Promise<string[]> {
  const { data } = await apiClient.get<string[]>(`${base}/documents`);
  return data;
}

export async function fetchDocument(docId: string): Promise<DocumentOut> {
  const { data } = await apiClient.get<DocumentOut>(
    `${base}/documents/${encodeURIComponent(docId)}`,
  );
  return data;
}

export async function fetchChapter(docId: string, index: number): Promise<ChapterOut> {
  const { data } = await apiClient.get<ChapterOut>(
    `${base}/documents/${encodeURIComponent(docId)}/chapters/${index}`,
  );
  return data;
}

export async function submitAnswer(args: {
  docId: string;
  sectionId: string;
  correct: boolean;
  conceptKey?: string;
}): Promise<AnswerOut> {
  const { data } = await apiClient.post<AnswerOut>(
    `${base}/documents/${encodeURIComponent(args.docId)}/sections/${args.sectionId}/answer`,
    { correct: args.correct, conceptKey: args.conceptKey ?? null },
  );
  return data;
}
