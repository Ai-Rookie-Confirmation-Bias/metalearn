// 파싱 진행 상황은 **서버가 진실**이다. 화면은 폴링해서 비출 뿐이다.
import { useQueries } from "@tanstack/react-query";

import {
  fetchParsingDocument,
  isSettled,
  type ParsingDocumentOut,
} from "@/features/parsing/api/documents";

export const parsingKeys = {
  document: (documentId: string) => ["parsing", "document", documentId] as const,
};

// 파이프라인은 분 단위(실측 probe.pdf 한 권)라 촘촘히 물어볼 이유가 없다.
const POLL_MS = 2000;

/** 아직 안 끝난 문서들의 상태. ready·failed가 되면 폴링을 멈춘다. */
export function useParsingDocuments(documentIds: string[]) {
  return useQueries({
    queries: documentIds.map((id) => ({
      queryKey: parsingKeys.document(id),
      queryFn: () => fetchParsingDocument(id),
      refetchInterval: (query: { state: { data?: ParsingDocumentOut } }) =>
        query.state.data && isSettled(query.state.data.status) ? false : POLL_MS,
      // 창을 잠깐 가려도 파싱은 계속 돈다. 돌아왔을 때 옛 단계가 보이면 안 된다.
      refetchIntervalInBackground: true,
      retry: false,
    })),
  });
}
