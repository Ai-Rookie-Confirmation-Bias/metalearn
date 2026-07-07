import { useMutation, useQueryClient } from "@tanstack/react-query";

import { readCompleteSection } from "@/features/learning/api/readCompleteSection";

// tracked 0개 절의 '다 읽었어요' 완료 뮤테이션. 성공 시 트리(진행 상태) 무효화 → 재조회.
export function useReadComplete() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: readCompleteSection,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["courseTree"] });
    },
  });
}
