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
}
