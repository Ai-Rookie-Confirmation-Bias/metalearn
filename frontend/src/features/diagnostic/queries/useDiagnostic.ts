// [2단계] TanStack Query 훅. api를 래핑.
import { useMutation } from "@tanstack/react-query";

import {
  startDiagnostic,
  submitAnswer,
  type AnswerInput,
} from "@/features/diagnostic/api/diagnosticApi";

export function useStartDiagnostic() {
  return useMutation({
    mutationFn: (materialId: number) => startDiagnostic(materialId),
  });
}

interface AnswerArgs {
  sessionId: number;
  questionId: number;
  input: AnswerInput;
}

export function useSubmitAnswer() {
  return useMutation({
    mutationFn: ({ sessionId, questionId, input }: AnswerArgs) =>
      submitAnswer(sessionId, questionId, input),
  });
}
