// 백엔드 Pydantic DTO(diagnostic/schemas.py)와 1:1 대응.
export type QuestionType = "mcq" | "cloze" | "inverse";

export interface QuestionOut {
  id: number;
  concept_id: number;
  concept_name: string;
  qtype: QuestionType;
  question: string;
  options: string[]; // mcq에서만 채워짐
}

export interface MasteryOut {
  concept_id: number;
  concept_name: string;
  p_known: number;
  resolved: boolean;
  answered_count: number;
}

export interface Progress {
  total: number;
  resolved: number;
}

export interface SessionState {
  session_id: number;
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
