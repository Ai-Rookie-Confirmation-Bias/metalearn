import { useMutation } from "@tanstack/react-query";

import { submitAttempt } from "@/features/learning/api/submitAttempt";

// 페이지가 onAnswer 구현에 쓰는 채점 뮤테이션. mutateAsync로 결과를 블록에 돌려준다.
export function useSubmitAttempt() {
  return useMutation({ mutationFn: submitAttempt });
}
