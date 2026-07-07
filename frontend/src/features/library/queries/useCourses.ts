// [2단계] TanStack Query 훅 — 책장 목록. 화면은 이 훅만 쓴다.
import { useQuery } from "@tanstack/react-query";

import { getCourses } from "@/features/library/api/getCourses";

export function useCourses() {
  return useQuery({
    queryKey: ["courses"],
    queryFn: getCourses,
  });
}
