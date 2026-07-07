import { useMutation } from "@tanstack/react-query";

import { uploadDocument } from "@/features/documents/api/uploadDocument";

interface UploadArgs {
  file: File;
  title?: string;
}

export function useUploadDocument() {
  return useMutation({
    mutationFn: ({ file, title }: UploadArgs) => uploadDocument(file, title),
  });
}
