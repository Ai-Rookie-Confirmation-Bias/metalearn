// [2단계] TanStack Query 훅. api를 래핑.
import { useMutation } from "@tanstack/react-query";

import {
  startDiagnostic,
  submitAnswer,
  type AnswerInput,
} from "@/features/diagnostic/api/diagnosticApi";

export function useStartDiagnostic() {
  return useMutation({
    mutationFn: (courseId: string) => startDiagnostic(courseId),
  });
}

interface AnswerArgs {
  sessionId: string;
  questionId: string;
  input: AnswerInput;
}

export function useSubmitAnswer() {
  return useMutation({
    mutationFn: ({ sessionId, questionId, input }: AnswerArgs) =>
      submitAnswer(sessionId, questionId, input),
  });
}
