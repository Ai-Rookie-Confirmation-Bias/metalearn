// 수업 생성 플로우 타입 — docs/SCHEMA.md 기준.

export type DocumentKind = "textbook" | "slide" | "notes" | "exam" | "link" | "text";
export type Purpose = "exam" | "career" | "culture" | "hobby";

// 업로드한 자료 한 건 (documents + course_documents.role 를 클라에서 임시 표현).
// 순서(분할 메인)는 배열 인덱스로 관리.
export type Material = {
  id: string;
  name: string; // 파일명 또는 링크 URL
  kind: DocumentKind;
  role: "primary" | "supplementary";
  file?: File; // 실제 업로드할 파일 객체 (링크는 없음)
};

// POST /courses 요청 바디 모양 (백엔드 붙으면 이대로 전송).
export type CreateCoursePayload = {
  documentIds: string[]; // 업로드 후 서버가 준 documentId들
  primaryIds: string[]; // 그중 메인
  purpose: Purpose;
};

// 책장에 잠깐 뜨는 "생성 중" 코스 (mock 대역).
export type DraftCourse = {
  id: string;
  title: string;
  generating: boolean;
};
