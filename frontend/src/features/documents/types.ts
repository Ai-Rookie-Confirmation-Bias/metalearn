// 백엔드 Pydantic DTO(documents/schemas.py)와 1:1 대응.
export interface ConceptOut {
  id: number;
  name: string;
  description: string;
  depth_level: number;
  prerequisite_ids: number[];
}

export interface CourseSummary {
  id: number;
  document_id: number;
  title: string;
  filename: string;
  status: string;
  created_at: string;
}

export interface CourseDetail extends CourseSummary {
  concept_count: number;
  concepts: ConceptOut[];
}
