// [2단계] TanStack Query 훅. api를 래핑.
import { useMutation } from "@tanstack/react-query";

import { uploadMaterial } from "@/features/materials/api/uploadMaterial";

interface UploadArgs {
  file: File;
  title?: string;
}

export function useUploadMaterial() {
  return useMutation({
    mutationFn: ({ file, title }: UploadArgs) => uploadMaterial(file, title),
  });
}
