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
  // ✚ 진단이 끼운 보강 단원 — 교재에 없던 내용이라 구분해 보여준다
  inserted: boolean;
  // 📚 그 내용을 이미 가르치는 자료가 책장에 있으면 그 한 줄.
  // 비어 있으면 AI가 쓴 것이다 — 화면이 두 경우를 다르게 말한다.
  coveredBy?: string;
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
  // 기본 제공 자료(공개 교재·픽스처)인가. 책장이 이걸로 두 칸을 가른다 —
  // 내가 올린 적 없는 책이 "내 자료"에 섞여 있으면 안 된다.
  shared?: boolean;
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
  // ↻ 반복해서 틀린 선수 개념 때문에 **우리가 끼운 보충 화면**.
  // 교재에 원래 있던 화면과 구분해 보여준다 — 안 그러면 원문이라고 오해한다.
  // 진도 분모에는 안 들어간다(백엔드에서 이미 빠져 나온다).
  inserted: boolean;
}

export interface ChapterOut {
  docId: string;
  docTitle: string;
  index: number;
  title: string;
  pages: string;
  inserted: boolean; // ✚ 진단이 끼운 보강 단원
  // 📚 그 내용을 이미 가르치는 자료가 책장에 있으면 그 한 줄.
  coveredBy?: string;
  readiness: number;
  ratio: number;
  progress: number;
  recall: number;
  sectionsDue: number;
  mode: PlanMode;
  reason: string;
  weakConcepts: string[];
  sections: SectionOut[];
  // 목차 마지막 항목(단원 평가)이 열렸는가. **화면이 판정하지 않는다** —
  // 문턱을 프론트에도 두면 규칙이 두 곳에 생기고 언젠가 갈라진다.
  formativeReady: boolean;
  formativeReason: string; // 잠겼을 때 얼마나 더 해야 하는지
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

/** 교재에 실려 있던 그림. 바이트는 파싱이 서빙하고 여기엔 주소만 온다. */
export interface FigureOut {
  figureId: string;
  page: number;
  caption: string;
  // 파싱이 "텍스트만으로 불완전"이라 본 그림 — 화면이 크게 놓을 근거
  needsVision: boolean;
  url: string;
  // 화면 안에서 어느 개념 옆에 놓을 것인가. 빈 값이면 자리를 못 정한 그림이라
  // 화면이 맨 뒤에 모아 놓는다 — 버리지 않는다.
  conceptKey?: string;
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
  figures: FigureOut[]; // 이 화면 구간에 있던 교재 그림
  // ⚡ 최근 틀린 개념 중 이 설명이 **실제로 엮은 것**. 비어 있으면 ⚡를 안 띄운다
  tiedIn: string[];
  covered: number;
  missing: string[];
  retrievalGap: string[];
  generated: boolean;
}

export interface FormativeOut {
  docId: string;
  chapterIndex: number;
  chapterTitle: string;
  // 🔒 학습은 안 잠그고 평가만 잠근다. 진도로만 — 이해도로 잠그면 못 하는
  // 사람일수록 확인할 기회가 사라진다
  locked: boolean;
  reason: string; // 잠겼을 때 얼마나 더 해야 하는지. 열려 있으면 빈 문자열
  progress: number;
  blocks: BlockOut[];
  crossing: number; // 화면을 가로지른 문항 수. 낮으면 인출 몰아보기와 같다
  coveredWeak: string[]; // 이 평가가 실제로 확인하는 약점(요청이 아니라 들어간 것)
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

export async function fetchFormative(
  docId: string,
  index: number,
): Promise<FormativeOut> {
  const { data } = await apiClient.get<FormativeOut>(
    `${base}/documents/${encodeURIComponent(docId)}/chapters/${index}/formative`,
  );
  return data;
}

export async function fetchLesson(docId: string, sectionId: string): Promise<LessonOut> {
  const { data } = await apiClient.get<LessonOut>(
    `${base}/documents/${encodeURIComponent(docId)}/sections/${sectionId}`,
  );
  return data;
}

/** 앞 N개 화면을 서버 캐시에 미리 올린다.
 *
 * 화면 하나를 처음 열면 LLM 콜이라 **cold 5~7초**다. 자료를 연 사람은 곧
 * 첫 화면을 누르므로, 개요를 보는 동안 서버가 미리 만들어 두면 클릭이
 * 즉시 열린다(실측 5.5초 → 0.00초).
 *
 * ⚠️ 결과를 기다리지 않는다. 이건 **없어도 되는 최적화**라, 실패하거나
 *    느려도 화면이 그것 때문에 막히면 안 된다.
 */
export function prewarm(docId: string, limit = 6): void {
  void apiClient
    .post(
      `${base}/documents/${encodeURIComponent(docId)}/prewarm?limit=${limit}`,
      undefined,
      { timeout: 300000 },
    )
    .catch(() => {});
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

// 복습 큐 — 망각곡선이 불러온 화면들.
// ⚠️ 설명은 안 온다(복습이지 재학습이 아니다). 한 번도 못 맞힌 화면도 안 온다.
export interface ReviewItem {
  sectionId: string;
  title: string;
  chapterIndex: number;
  chapterTitle: string;
  recall: number;
  daysSince: number;
  blocks: BlockOut[];
}

export interface ReviewOut {
  docId: string;
  shiftedDays: number; // 시연용 시계 이동. 진짜 곡선을 시간만 옮겨 본다
  totalDue: number;
  items: ReviewItem[];
}

export async function fetchReview(docId: string, days = 0): Promise<ReviewOut> {
  const { data } = await apiClient.get<ReviewOut>(
    `${base}/documents/${encodeURIComponent(docId)}/review`,
    { params: { days } },
  );
  return data;
}
