import { useQuery } from "@tanstack/react-query";

import { getReviewDue } from "@/features/review/api/getReviewDue";

export function useReviewDue(courseId?: string) {
  return useQuery({
    queryKey: ["reviewDue", courseId ?? null],
    queryFn: () => getReviewDue(courseId),
  });
}
