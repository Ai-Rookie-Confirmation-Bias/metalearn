// 백엔드 Pydantic DTO(documents/schemas.py)와 1:1 대응.
// UUID 포팅: 모든 id는 UUID 문자열 (기존 int → string).
export interface ConceptOut {
  id: string;
  name: string;
  description: string;
  depth_level: number;
  /** 'document' = 교재에서 추출, 'llm' = LLM이 보충한 선수개념 */
  source: "document" | "llm";
  /** 교재 추출 개념의 원문 섹션(헤딩 경로) */
  source_anchor: string | null;
  prerequisite_ids: string[];
}

export interface CourseSummary {
  id: string;
  document_id: string;
  title: string;
  filename: string;
  status: string;
  created_at: string;
}

export interface CourseDetail extends CourseSummary {
  concept_count: number;
  concepts: ConceptOut[];
}
