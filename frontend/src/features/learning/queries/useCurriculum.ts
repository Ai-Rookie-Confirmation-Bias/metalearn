// [2단계] TanStack Query 훅. api를 래핑.
import { useMutation } from "@tanstack/react-query";

import {
  requestCurriculum,
  type CurriculumArgs,
} from "@/features/learning/api/requestCurriculum";

export function useCurriculum() {
  return useMutation({
    mutationFn: (args: CurriculumArgs) => requestCurriculum(args),
  });
}
