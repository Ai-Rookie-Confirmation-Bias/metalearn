// 수업 생성 플로우 타입 — docs/SCHEMA.md 기준.

export type DocumentKind = "textbook" | "slide" | "notes" | "exam" | "link" | "text";
export type Purpose = "exam" | "career" | "culture" | "hobby";

// 업로드한 자료 한 건. 파일을 고르는 순간 서버로 올라가므로 화면에 사는 동안
// 상태가 셋 중 하나다 — 올리는 중 / 접수됨(docId 있음) / 실패.
// 파싱 진행 상황은 여기 없다. 그건 접수 후 서버에 물어본다.
export type Material = {
  id: string; // 화면 안에서만 쓰는 행 id (서버 id는 docId)
  name: string;
  size: number; // bytes
  kind: DocumentKind;
  role: "primary" | "supplementary";
  docId?: string; // 업로드 성공 시 서버가 준 파싱 문서 UUID
  error?: string; // 실패 사유. 있으면 이 행은 제출에 못 들어간다
};

// POST /courses 요청 바디 모양 (백엔드 붙으면 이대로 전송).
// ⚠️ 아직 안 부른다 — 코스 목록 API가 없어 책장이 코스가 아니라 자료 단위다.
export type CreateCoursePayload = {
  documentIds: string[]; // 업로드 후 서버가 준 documentId들
  primaryIds: string[]; // 그중 메인
  purpose: Purpose;
};
