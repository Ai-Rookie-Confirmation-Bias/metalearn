import { useQuery } from "@tanstack/react-query";

import { getSectionBlocks } from "@/features/learning/api/getSectionBlocks";

export function useSectionBlocks(sectionId: string | undefined) {
  return useQuery({
    queryKey: ["sectionBlocks", sectionId],
    queryFn: () => getSectionBlocks(sectionId as string),
    enabled: !!sectionId,
  });
}
