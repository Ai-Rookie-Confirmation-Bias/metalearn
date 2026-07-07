import { apiClient } from "@/shared/api/client";
import type { CourseDetail } from "@/features/documents/types";

export async function uploadDocument(
  file: File,
  title?: string,
): Promise<CourseDetail> {
  const form = new FormData();
  form.append("file", file);
  if (title) form.append("title", title);

  const { data } = await apiClient.post<CourseDetail>(
    "/api/documents/upload",
    form,
    { headers: { "Content-Type": "multipart/form-data" }, timeout: 300_000 },
  );
  return data;
}
