import { useQuery } from "@tanstack/react-query";

import { getMastery } from "@/features/analysis/api/getMastery";

export function useMastery(courseId: string | undefined) {
  return useQuery({
    queryKey: ["mastery", courseId],
    queryFn: () => getMastery(courseId as string),
    enabled: !!courseId,
  });
}
