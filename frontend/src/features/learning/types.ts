export interface StartSessionResponse {
  session_id: string;
  question: string;
}

export interface RespondCorrectResponse {
  correct: true;
  feedback: string;
}

export interface RespondIncorrectResponse {
  correct: false;
  hint: string;
  missing_concept: string;
  reason: string;
}

export type RespondResponse = RespondCorrectResponse | RespondIncorrectResponse;

export type TutorStepType = "question" | "hint_1" | "hint_2" | "answer_reveal";

export interface WeaknessEntry {
  concept_id: string;
  missing_concept: string;
  reason: string;
}

export interface HintResponse {
  step_type: TutorStepType;
  content: string;
}

export interface CompleteSessionResponse {
  concept_id: string;
  resolved: boolean;
  current_weaknesses: WeaknessEntry[];
  return_to_session_id?: string | null;
}

export interface StartPrerequisiteResponse {
  session_id: string;
  prereq_concept_title: string;
  why: string;
  question: string;
  depth: number;
  is_foundational: boolean;
}

// ── 적응형 학습 블록 타입 ──────────────────────────────────────────────────────

export interface BlockMeta {
  difficulty: string;
  density: "thin" | "normal" | "thick";
  depth: number;
  version: number;
}

// 프론트 카탈로그 type별 data (1차 필수 5종)
export interface ConceptBlockData {
  title: string;
  body: string;
  source: "book" | "ai";
}
export interface ExplainBackBlockData {
  prompt: string;
  rubric: string[];
}
export interface McqBlockData {
  question: string;
  options: string[];
  answerIndex: number;
  explanation?: string;
}
export interface ClozeBlockData {
  segments: { text?: string; blank?: boolean }[];
  answers: string[];
  aliases?: string[][];
}
export interface ReviewGateBlockData {
  concepts: string[];
  dueItems: unknown[];
}

export interface BlockResponse {
  id: string;
  type: "concept" | "explainBack" | "mcq" | "cloze" | "reviewGate" | string;
  conceptId: string;
  source: "book" | "ai";
  data: Record<string, unknown>;
  meta: BlockMeta;
  // 적응형 흐름 정보 (프론트는 몰라도 무방)
  actionType: "teach" | "quiz" | "advance" | "thin_pass" | "supplement" | "prerequisite";
  actionReason: string;
}

export interface BlockAnswerRequest {
  profileId: string;
  conceptId: string;
  userInput: string;
  blockId?: string;
  // cloze/mcq 처럼 프론트 채점 가능하면 채움, explainBack 등은 생략(백엔드 채점)
  correct?: boolean | null;
}

export interface BlockAnswerResponse {
  correct: boolean;
  feedback: string;
  masteryScore: number;
  nextAction: string;
  consecutiveWrong: number;
  weaknessRegistered: boolean;
  curriculumChanged: boolean;
  insertedUnitTitle?: string | null;
  currentUnitOrder: number;
}

export interface LearnerModelResponse {
  profileId: string;
  conceptMastery: Record<string, { score: number; attempts: number; lastSeen: string }>;
  currentUnitOrder: number;
  updatedAt: string;
}
