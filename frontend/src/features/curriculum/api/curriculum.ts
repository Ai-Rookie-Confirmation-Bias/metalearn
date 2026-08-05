// [1단계] 커리큘럼 백엔드 호출.
//
// 판단은 전부 백엔드에서 끝나 있다. 여기서 계산하거나 문구를 만들지 않는다 —
// reason은 규칙이 만든 문장이라 그대로 화면에 나가야 "왜 이렇게 나왔는지"가
// 검증 가능한 상태로 유지된다.
import { apiClient } from "@/shared/api/client";

export type MasteryStatus = "untouched" | "learning" | "weak" | "shaky" | "solid";
export type PlanMode = "deep" | "normal" | "compressed";

// 문항을 푸는 자리 넷. 전부 같은 문으로 들어와 하나의 누적값이 된다.
// 한 문항이 담는 정보량이 달라 백엔드가 출처별로 가중한다.
export type AttemptKind = "diagnostic" | "retrieval" | "review" | "formative";

export const KIND_LABEL: Record<AttemptKind, string> = {
  diagnostic: "진단",
  retrieval: "학습",
  review: "복습",
  formative: "평가",
};

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
  recall: number; // 회상 강도 — 지금도 꺼내지나
  sectionsDue: number; // 🔁 복습이 필요한 절 수
  mode: PlanMode;
  reason: string; // ⚡ 비어 있으면 아직 판단 근거가 없다는 뜻
}

export interface DocumentOut {
  docId: string;
  title: string;
  // 준비도 = 이해도 × 진도 × 회상. 네 출처가 모여 나오는 하나의 값
  readiness: number;
  // 망각을 뺀 값. 준비도가 낮은 게 "잊은 것"인지 "아직 모르는 것"인지 가른다
  understanding: number;
  complete: boolean;
  sectionsTotal: number;
  remainingSections: number;
  sectionsDue: number;
  estimatedMinutes: number;
  weakestChapter: number | null;
  byKind: Partial<Record<AttemptKind, number>>; // 누적이 어디서 왔는지
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
  recall: number;
  needsReview: boolean; // 🔁 맞힌 적 있는데 잊혀가는 절
  byKind: Partial<Record<AttemptKind, number>>;
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
  recall: number;
  sectionsDue: number;
  mode: PlanMode;
  reason: string;
  weakConcepts: string[];
  sections: SectionOut[];
}

export type BlockType = "concept" | "analogy" | "tie_in" | "cloze" | "mcq";

export interface BlockOut {
  type: BlockType;
  // 종류마다 모양이 다르다:
  //   concept {text} · analogy {text,label} · tie_in {text,label}
  //   cloze {sentence,answer} · mcq {question,options,answer,explanation}
  content: Record<string, unknown>;
  conceptKeys: string[];
}

export interface LessonOut {
  sectionId: string;
  docId: string;
  chapterIndex: number;
  chapterTitle: string;
  title: string;
  concepts: string[];
  reason: string;
  page: string;
  status: MasteryStatus;
  statusLabel: string;
  blocks: BlockOut[];
  source: string; // 📎 교재 원문 그대로. 요약이 아니다
  // ⚡ 최근 틀린 개념 중 이 설명이 **실제로 엮은 것**. 비어 있으면 ⚡를 안 띄운다
  tiedIn: string[];
  covered: number;
  missing: string[];
  retrievalGap: string[];
  generated: boolean;
}

export interface AnswerOut {
  sectionId: string;
  status: MasteryStatus;
  statusLabel: string;
  attempts: number;
  improving: boolean;
  recall: number;
  chapterRatio: number;
  chapterMode: PlanMode;
  chapterReason: string;
  readiness: number;
  understanding: number;
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

export async function fetchLesson(docId: string, sectionId: string): Promise<LessonOut> {
  const { data } = await apiClient.get<LessonOut>(
    `${base}/documents/${encodeURIComponent(docId)}/sections/${sectionId}`,
  );
  return data;
}

// 네 출처가 전부 이 문으로 들어간다. kind를 안 넘기면 인출로 친다 —
// 지금 화면에서 오는 건 전부 인출이고, 진단·복습·형성은 붙을 때 명시하면 된다.
export async function submitAnswer(args: {
  docId: string;
  sectionId: string;
  correct: boolean;
  conceptKey?: string;
  kind?: AttemptKind;
}): Promise<AnswerOut> {
  const { data } = await apiClient.post<AnswerOut>(
    `${base}/documents/${encodeURIComponent(args.docId)}/sections/${args.sectionId}/answer`,
    {
      correct: args.correct,
      conceptKey: args.conceptKey ?? null,
      kind: args.kind ?? "retrieval",
    },
  );
  return data;
}
