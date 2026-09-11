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
  // MetaLearn 도서관에서 고른 책인가. 올린 게 아니라 **이미 있는 것을 가리킨** 행이라
  // 파일 크기도 없고 유형도 못 바꾼다 — 공용 문서라 내 위저드가 남의 책 속성을
  // 덮어쓰면 그 책을 쓰는 다른 사람에게도 그대로 간다.
  fromLibrary?: boolean;
};
