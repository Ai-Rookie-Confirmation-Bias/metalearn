import { useQuery } from "@tanstack/react-query";

import { getCourseTree } from "@/features/learning/api/getCourseTree";

export function useCourseTree(courseId: string | undefined) {
  return useQuery({
    queryKey: ["courseTree", courseId],
    queryFn: () => getCourseTree(courseId as string),
    enabled: !!courseId,
  });
}
