import { useMutation } from "@tanstack/react-query";

import { submitReviewAnswer } from "@/features/review/api/submitReviewAnswer";

export function useSubmitReviewAnswer() {
  return useMutation({ mutationFn: submitReviewAnswer });
}
