// 자료 업로드와 파싱 상태 조회.
//
// ⚠️ 파싱 API는 snake_case다(커리큘럼은 camelCase). 어느 쪽으로 맞출지는
// 아직 안 정해졌으므로(docs/INTEGRATION.md §3) 여기서 임의로 바꾸지 않고
// 응답 모양 그대로 받는다. 바꾸면 계약이 두 벌이 된다.
import { apiClient } from "@/shared/api/client";

// backend/app/features/parsing/models.py DocStatus 그대로.
export type ParseStatus =
  | "pending"
  | "parsing"
  | "refining"
  | "segmenting"
  | "topics"
  | "extracting"
  | "ready"
  | "failed";

export interface ParsingDocumentOut {
  id: string;
  filename: string;
  source_format: string;
  status: ParseStatus;
  error: string | null;
  parser_version: string;
  density_grade: string | null;
  avg_segment_chars: number | null;
  concept_coverage: number | null;
  created_at: string;
}

// 파이프라인이 지나는 순서. 진행 막대의 분모이자 문구의 출처다 —
// 화면이 단계를 세지 않는다, 서버가 준 status를 이 표에서 찾을 뿐이다.
const STAGES: ParseStatus[] = [
  "pending",
  "parsing",
  "refining",
  "segmenting",
  "topics",
  "extracting",
];

export const PARSE_LABEL: Record<ParseStatus, string> = {
  pending: "차례를 기다리는 중",
  parsing: "문서를 읽는 중",
  refining: "군더더기를 걷어내는 중",
  segmenting: "원문을 조각내는 중",
  topics: "목차를 잡는 중",
  extracting: "개념을 뽑는 중",
  ready: "학습 준비 완료",
  failed: "분석에 실패했어요",
};

/** 0~1. 단계 수로만 나눈 값이라 시간 비례가 아니다 — 멈춘 게 아님을 보이는 용도. */
export function parseProgress(status: ParseStatus): number {
  if (status === "ready") return 1;
  if (status === "failed") return 0;
  return Math.max(0, STAGES.indexOf(status)) / STAGES.length;
}

export function isSettled(status: ParseStatus): boolean {
  return status === "ready" || status === "failed";
}

// Document Parse가 받는 확장자. backend/…/adapters/document_parse.py `_FORMATS`가 정본.
export const ACCEPT_EXTENSIONS = ".pdf,.png,.jpg,.jpeg,.tiff,.bmp,.heic";

/**
 * 업로드 → 백그라운드 파싱 시작(202). 응답은 파싱 결과가 아니라 **접수증**이다.
 *
 * 같은 파일(지문 일치)은 다시 파싱하지 않고 기존 문서를 그대로 돌려준다.
 * 그래서 실수로 지웠다 다시 올리는 비용이 0이다.
 *
 * `role` 파라미터는 보내지 않는다 — 서버가 그 값을 user_documents에만 쓰는데
 * user_id가 없으면 아예 저장되지 않는다(users 테이블이 아직 없다).
 * 반영도 안 되는 값을 보내면 "역할을 정했다"는 착각만 남는다.
 */
export async function uploadDocument(file: File): Promise<ParsingDocumentOut> {
  const form = new FormData();
  form.append("file", file);
  // 파싱은 백그라운드지만 서버가 파일을 다 읽은 뒤에 응답한다. 공통 30초로는
  // 큰 교재가 걸린다(파싱 실행기도 같은 이유로 120초를 쓴다).
  const { data } = await apiClient.post<ParsingDocumentOut>(
    "/api/parsing/documents",
    form,
    { timeout: 120_000 },
  );
  return data;
}

export async function fetchParsingDocument(
  documentId: string,
): Promise<ParsingDocumentOut> {
  const { data } = await apiClient.get<ParsingDocumentOut>(
    `/api/parsing/documents/${encodeURIComponent(documentId)}`,
  );
  return data;
}
