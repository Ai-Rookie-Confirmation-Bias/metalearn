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

// 배치고사(placement, ISSUE-015) — 문항 1개씩 서빙, 바닥(floor)만 찾는다.
// 구형 진단(SessionState/AnswerResult)과 달리 문항별 정오답 피드백이 없다:
// 답하면 바로 다음 문항, done=true일 때 floor/ceiling + 시드 결과가 채워진다.
export interface PlacementState {
  session_id: string;
  done: boolean;
  asked: number; // 지금까지 답한 문항 수
  max_questions: number; // 상한(보통 12)
  question: QuestionOut | null; // 다음 문항(done이면 null)
  floor_concept: string | null;
  ceiling_concept: string | null;
  weak_concept_ids: string[];
  seed: unknown | null;
}

export interface AnswerResult {
  is_correct: boolean;
  correct_index: number | null;
  correct_answer: string | null;
  explanation: string;
  feedback: string | null; // 오답일 때 "왜 틀렸는지" (정답이면 null)
  mastery: MasteryOut;
  done: boolean;
  progress: Progress;
  next_question: QuestionOut | null;
}

// ── 온보딩 (진단 재설계) ─────────────────────────────────────────────
export type OnboardingPhase = "disposition" | "probe" | "quiz" | "done";

export interface DispositionItemOut {
  id: string;
  prompt: string;
  options: string[];
}

export interface ProbeOut {
  concept_id: string;
  concept_name: string;
  variant_a: string;
  variant_b: string;
}

export interface FoundationGapOut {
  concept_id: string;
  concept_name: string;
  missing: string[];
}

export interface OnboardingResult {
  label: string;
  traits: string[];
  axes: Record<string, { score: number; confidence: number; n: number }>;
  foundation_gaps: FoundationGapOut[];
  injected_prereqs: string[];
  seeded: number;
}

export interface OnboardingReveal {
  correct: boolean;
  correct_answer: string;
}

export interface OnboardingState {
  session_id: string;
  phase: OnboardingPhase;
  step: number;
  total_steps: number;
  done: boolean;
  disposition: DispositionItemOut | null;
  probe: ProbeOut | null;
  question: QuestionOut | null;
  result: OnboardingResult | null;
  // 직전 기반지식 문항의 정답(표시용) — quiz phase 답변 직후에만 채워진다.
  last_reveal?: OnboardingReveal | null;
}
