// 백엔드 learning/schemas.py CurriculumResponse 와 대응.
export type CurriculumMode = "focused" | "bridge";

export interface CurriculumBlock {
  kind: "chapter" | "prose" | "cloze" | "inverse";
  // chapter
  title?: string;
  // prose / chapter
  heading?: string;
  text?: string;
  // inverse
  prompt?: string;
  // cloze/inverse
  answer?: string;
}

export interface CurriculumResponse {
  id: number;
  concept_id: number;
  concept_name: string;
  score: number;
  mode: CurriculumMode;
  prerequisite_ratio: number;
  main_ratio: number;
  prerequisite_names: string[];
  blocks: CurriculumBlock[];
}
