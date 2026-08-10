// 드래그해서 물어보기.
//
// ⚠️ 커리큘럼 API라 **camelCase다**(파싱은 snake_case).
//
// 근거 검색은 서버가 한다. 화면은 "무엇을 끌었는지"와 "어느 문단이었는지"만
// 보내고, 어느 교재에서 찾을지는 서버가 정한다 — 인용 범위를 화면이 정하면
// 남의 사적인 교재까지 뒤지는 요청을 만들 수 있다.
import { apiClient } from "@/shared/api/client";

export interface AskSource {
  documentId: string;
  filename: string;
  concept: string;
  definition: string;
  topicTitle: string | null;
  page: string | null;
  similarity: number;
  /** 지금 읽는 자료가 아니라 MetaLearn 도서관 책에서 왔나. */
  shared: boolean;
}

export interface AskOut {
  answer: string;
  /** 이 화면을 만들 때 쓴 교재 원문을 근거로 썼나. 이게 이 기능의 본체다 —
   *  없으면 그냥 AI가 아는 대로 답한 것이고, 화면이 둘을 갈라 말해야 한다. */
  grounded: boolean;
  page: string | null;
  /** 다른 자리(다른 단원 · 📕 도서관 책)에서 찾은 같은 개념. **더 볼 곳**이다. */
  sources: AskSource[];
}

export interface AskTurn {
  role: "user" | "assistant";
  content: string;
}

/** 서버와 같은 상한(`router.ask`). 여기서 먼저 막는 건 왕복을 아끼려는 것이다. */
export const MAX_SELECTION = 500;

export async function askAboutSelection(args: {
  docId: string;
  sectionId: string;
  selection: string;
  context: string;
  question?: string;
  history: AskTurn[];
}): Promise<AskOut> {
  const { docId, sectionId, ...body } = args;
  const { data } = await apiClient.post<AskOut>(
    `/api/curriculum/documents/${encodeURIComponent(docId)}/sections/${encodeURIComponent(sectionId)}/ask`,
    body,
    // 근거 검색(임베딩) + 생성이라 공통 30초로는 아슬아슬하다.
    { timeout: 60_000 },
  );
  return data;
}
