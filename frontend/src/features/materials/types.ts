// 백엔드 Pydantic DTO(materials/schemas.py)와 1:1 대응되는 타입.
export interface ConceptOut {
  id: number;
  name: string;
  description: string;
  depth: number;
  prerequisite_ids: number[];
}

export interface MaterialSummary {
  id: number;
  title: string;
  filename: string;
  status: string;
  created_at: string;
}

export interface MaterialDetail extends MaterialSummary {
  concept_count: number;
  concepts: ConceptOut[];
}
