import { useMutation, useQueryClient } from "@tanstack/react-query";

import { generateChapter } from "@/features/learning/api/generateChapter";

// 챕터 JIT 생성 트리거. 성공 시 트리(gen_status) 무효화 → 재조회.
export function useGenerateChapter() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: generateChapter,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["courseTree"] });
    },
  });
}
