// MetaLearn 도서관에 꽂힌 책 목록.
//
// 두 화면이 같은 목록을 쓴다 — 도서관 페이지(`/shared`)와 수업 생성 위저드의
// "도서관에서 찾아보기". 목록 API가 내 자료와 도서관 자료를 함께 주기 때문에
// `shared` 플래그로 거르는 일이 두 곳에 복붙되면 한쪽만 고쳐질 자리가 된다.
import { useQueries } from "@tanstack/react-query";

import {
  fetchDocument,
  type DocumentOut,
} from "@/features/curriculum/api/curriculum";
import { curriculumKeys, useDocuments } from "./useCurriculum";

/** 이 책으로 수업을 만들 수 있나.
 *
 * 도서관에는 두 종류가 섞여 있다 — 실제로 파싱한 공개 문서(`docId`가 파싱
 * 문서 UUID 그대로)와, 데모용 픽스처(`sample_sdlc` 같은 슬러그). 수업은
 * `document_ids`로 만드는데 픽스처는 `documents` 테이블에 행이 없어서
 * 서버가 "자료를 찾을 수 없습니다"로 거절한다.
 *
 * 그래서 **모양으로 가른다.** 서버가 이 구분을 따로 알려주지 않는다 —
 * 알려주게 되면 이 함수를 지우고 그 필드를 쓰면 된다.
 */
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function canBecomeCourse(docId: string): boolean {
  return UUID.test(docId);
}

/** 검색 한 건. `via`는 **제목이 아니라 목차에서 걸렸을 때** 그 목차 제목이다. */
export type BookHit = { doc: DocumentOut; via: string | null };

/** 책 찾기 — 제목과 **목차까지** 본다.
 *
 * 책 이름을 알고 오는 사람은 드물다. "난수"를 배우려는 사람이 『점프 투 파이썬』을
 * 떠올릴 이유가 없으므로, 목차에 있으면 걸려야 한다. 목차는 이미 받아 온 값이라
 * 서버를 더 부르지 않는다.
 *
 * 목차에서 걸린 건 **왜 떴는지 화면에 말해야 한다.** 제목에 없는 책이 검색
 * 결과에 있으면 사용자는 목록을 의심한다.
 *
 * 도서관 페이지와 수업 생성 위저드가 같이 쓴다 — 두 곳에서 다르게 찾으면
 * 같은 검색어에 다른 결과가 나온다.
 */
export function searchBooks(books: DocumentOut[], query: string): BookHit[] {
  const q = query.trim().toLowerCase();
  if (!q) return books.map((doc) => ({ doc, via: null }));

  const hits: BookHit[] = [];
  for (const doc of books) {
    if (doc.title.toLowerCase().includes(q)) {
      hits.push({ doc, via: null });
      continue;
    }
    const chapter = doc.chapters.find((c) => c.title.toLowerCase().includes(q));
    if (chapter) hits.push({ doc, via: chapter.title });
  }
  return hits;
}

export function useSharedLibrary(): {
  books: DocumentOut[];
  isLoading: boolean;
  isError: boolean;
} {
  const { data: docIds, isLoading, isError } = useDocuments();

  const docs = useQueries({
    queries: (docIds ?? []).map((id) => ({
      queryKey: curriculumKeys.document(id),
      queryFn: () => fetchDocument(id),
    })),
  });

  const books = docs
    .map((q) => q.data)
    .filter((d): d is DocumentOut => Boolean(d) && Boolean(d!.shared));

  return { books, isLoading, isError };
}
