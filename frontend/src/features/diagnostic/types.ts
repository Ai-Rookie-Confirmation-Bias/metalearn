// 백엔드 Pydantic DTO(diagnostic/schemas.py)와 1:1 대응.
// UUID 포팅: 모든 id는 서버가 UUID 문자열로 내려준다 (기존 int → string).
export type QuestionType = "mcq" | "cloze" | "inverse";

export interface QuestionOut {
  id: string;
  concept_id: string;
  concept_name: string;
  qtype: QuestionType;
  question: string;
  options: string[]; // mcq에서만 채워짐
}

export interface MasteryOut {
  concept_id: string;
  concept_name: string;
  strength: number;
  resolved: boolean;
  answered_count: number;
}

export interface Progress {
  total: number;
  resolved: number;
  // 문항 기준 진행 (신규 필드 — 구버전 응답엔 없을 수 있어 optional).
  answered_questions?: number; // 이번 세션에서 답변한 문항 수
  question_cap?: number; // 세션 총 문항 상한
}

export interface SessionState {
  session_id: string;
  status: string;
  done: boolean;
  progress: Progress;
  question: QuestionOut | null;
  masteries: MasteryOut[];
}

export interface AnswerResult {
  is_correct: boolean;
  correct_index: number | null;
  correct_answer: string | null;
  explanation: string;
  mastery: MasteryOut;
  done: boolean;
  progress: Progress;
  next_question: QuestionOut | null;
}
