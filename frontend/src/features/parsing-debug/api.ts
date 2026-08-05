import { apiClient } from "@/shared/api/client";

export type StepMeta = {
  id: string;
  label: string;
  kind: "호출" | "로직";
  solar: number;
  desc: string;
};

export type StepResult = {
  step: string;
  label: string;
  elapsed_ms: number;
  solar_calls: number;
  summary: Record<string, unknown>;
  preview: Record<string, unknown>[];
  note: string | null;
};

export type DebugState = {
  document_id: string;
  filename: string;
  status: string;
  error: string | null;
  done: string[];
  counts: {
    elements: number;
    figures: number;
    figures_located: number;
    segments: number;
    sentences: number;
    topics: number;
    concepts: number;
    edges: number;
  };
  density_grade: string | null;
};

/** 1단계 원문 — 자르지 않은 요소 하나. */
export type RawElement = {
  idx: number;
  id: number | null;
  category: string | null;
  page: number | null;
  removed: string | null;
  has_image: boolean;
  text: string;
};

export type RawQuality = {
  elements: number;
  pages: number;
  chars: number;
  avg_chars: number;
  space_ratio: number;
  control_ratio: number;
  control_chars: number;
  control_names: string[];
  glued_ratio: number;
  unterminated_ratio: number;
  verdict: string;
  samples: string[];
};

export type RawDocument = {
  document_id: string;
  filename: string;
  markdown: string;
  quality: RawQuality;
  elements: RawElement[];
};

const BASE = "/api/parsing/debug";

export async function fetchSteps(): Promise<StepMeta[]> {
  const { data } = await apiClient.get<StepMeta[]>(`${BASE}/steps`);
  return data;
}

export async function uploadDocument(file: File): Promise<DebugState> {
  const form = new FormData();
  form.append("file", file);
  // Document Parse는 22p 기준 20초 넘게 걸린다 — 공통 30초 타임아웃으로는 부족.
  const { data } = await apiClient.post<DebugState>(`${BASE}/documents`, form, {
    timeout: 120_000,
  });
  return data;
}

export async function fetchState(documentId: string): Promise<DebugState> {
  const { data } = await apiClient.get<DebugState>(`${BASE}/${documentId}/state`);
  return data;
}

export async function runStep(
  documentId: string,
  step: string,
): Promise<{ result: StepResult; state: DebugState }> {
  // 개념 추출은 조각 수만큼 LLM을 부른다(21조각 ≈ 2분). 넉넉히 잡는다.
  const { data } = await apiClient.post(
    `${BASE}/${documentId}/steps/${step}`,
    null,
    { timeout: 600_000 },
  );
  return data;
}

export async function fetchRaw(documentId: string): Promise<RawDocument> {
  // 요소 수천 개 + 원문 전체라 응답이 수백 KB가 된다. 공통 타임아웃으로는 짧다.
  const { data } = await apiClient.get<RawDocument>(`${BASE}/${documentId}/raw`, {
    timeout: 120_000,
  });
  return data;
}

export function figureUrl(documentId: string, figureId: string): string {
  return `${apiClient.defaults.baseURL}${BASE}/${documentId}/figures/${figureId}`;
}
