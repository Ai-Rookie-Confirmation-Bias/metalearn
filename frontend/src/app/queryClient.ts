import { QueryClient } from "@tanstack/react-query";

// TanStack Query 전역 캐시/에러 옵션 설정
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 1000 * 30,
      refetchOnWindowFocus: false,
    },
  },
});
