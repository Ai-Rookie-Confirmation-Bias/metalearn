export type LearningGoal = "exam" | "concept_understanding" | "problem_solving" | "skim";

export interface TocEntry {
  id: string;
  title: string;
  start_page: number;
  end_page: number;
}

export interface ConceptEntry {
  id: string;
  title: string;
  page_numbers: number[];
  chunk_ids: string[];
  prior_concept_ids?: string[];
}

export interface DocumentSkeleton {
  document_id: string;
  page_count: number;
  toc: TocEntry[];
  concepts: ConceptEntry[];
  external_prerequisites: string[];
}

export interface PrerequisiteSuggestion {
  id: string;
  label: string;
  source: "in_document" | "external";
  reason: string;
  recommended: boolean;
}

export interface PrerequisiteAnalysis {
  suggestions: PrerequisiteSuggestion[];
  concepts_needing_prereq: string[];
  summary: string;
  generation_mode?: "llm" | "local";
  generation_note?: string | null;
}

export interface DocumentResponse {
  id: string;
  filename: string;
  page_count: number;
  parse_status: string;
  parse_engine?: "upstage" | "pypdf";
  parse_mode?: "llm" | "local";
  created_at: string;
}

export interface LearningRange {
  start: string;
  end: string;
}

export interface SurveyRequest {
  document_id: string;
  learning_range: LearningRange;
  known_before: string[];
  learning_goal?: LearningGoal | null;
}

export interface SeedProfileResponse {
  id: string;
  document_id: string;
  learning_range: LearningRange;
  known_before: string[];
  learning_goal: string | null;
  concepts_in_range: string[];
  weaknesses: string[];
  status: string;
  created_at: string;
}

export interface DiagnosticQuestion {
  id: string;
  concept_id: string;
  question_text: string;
  options: string[];
}

export interface DiagnosticSession {
  id: string;
  profile_id: string;
  status: string;
  questions: DiagnosticQuestion[];
  generation_mode?: "llm" | "fallback";
  generation_note?: string | null;
}

export interface AnswerItem {
  question_id: string;
  choice_index: number;
}

export interface DiagnosticResult {
  session_id: string;
  profile_id: string;
  weaknesses: string[];
  score: number;
  status: string;
}

export interface SeedSlice {
  document_id: string;
  profile_id: string;
  learning_range: LearningRange;
  known_before: string[];
  learning_goal: string | null;
  concepts_in_range: string[];
  weaknesses: string[];
}

export type CurriculumPriority = "weakness" | "standard";
export type CurriculumUnitStatus = "pending" | "in_progress" | "completed";

export interface CurriculumUnit {
  order: number;
  concept_id: string;
  title: string;
  page_numbers: number[];
  chunk_ids: string[];
  chapter_id: string | null;
  priority: CurriculumPriority;
  status: CurriculumUnitStatus;
  summary?: string | null;
  focus?: string | null;
  content?: string | null;
}

export interface CurriculumChapterGroup {
  chapter_id: string | null;
  chapter_title: string;
  units: CurriculumUnit[];
}

export interface Curriculum {
  id: string;
  profile_id: string;
  document_id: string;
  learning_goal: string | null;
  weakness_count: number;
  total_units: number;
  units: CurriculumUnit[];
  chapter_groups: CurriculumChapterGroup[];
  generation_mode?: "llm" | "local";
  generation_note?: string | null;
  created_at: string;
}

export const LEARNING_GOAL_LABELS: Record<LearningGoal, string> = {
  exam: "시험 대비",
  concept_understanding: "개념 이해",
  problem_solving: "문제 풀이",
  skim: "훑어보기",
};

export const PREREQUISITE_LABELS: Record<string, string> = {
  linear_algebra_basics: "선형대수 기초",
  calculus_basics: "미적분 기초",
  probability_basics: "확률 기초",
};
