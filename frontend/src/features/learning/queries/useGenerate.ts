// [2단계] TanStack Query 훅. api를 래핑.
import { useMutation } from "@tanstack/react-query";

import { requestGenerate } from "@/features/learning/api/requestGenerate";

export function useGenerate() {
  return useMutation({
    mutationFn: (topic: string) => requestGenerate(topic),
  });
}
