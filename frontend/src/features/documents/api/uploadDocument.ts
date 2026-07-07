import { apiClient } from "@/shared/api/client";
import type { CourseDetail } from "@/features/documents/types";

interface UploadAccepted {
  id: string; // course_id
  document_id: string;
  course_id: string;
  status: string;
}

const POLL_INTERVAL_MS = 3_000;
const POLL_TIMEOUT_MS = 30 * 60_000; // 대형 문서 대비 여유

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

/**
 * 비동기 ingest(ISSUE-010②): 업로드는 즉시 접수(processing)되고 파이프라인은
 * 서버 백그라운드에서 돈다. 여기서 상태를 폴링해 완성된 CourseDetail을
 * 반환하므로 호출부 계약은 기존(동기 업로드)과 동일하다.
 */
export async function uploadDocument(
  file: File,
  title?: string,
): Promise<CourseDetail> {
  const form = new FormData();
  form.append("file", file);
  if (title) form.append("title", title);

  const { data: accepted } = await apiClient.post<UploadAccepted>(
    "/api/documents/upload",
    form,
    { headers: { "Content-Type": "multipart/form-data" }, timeout: 60_000 },
  );

  const courseId = accepted.course_id ?? accepted.id;
  const deadline = Date.now() + POLL_TIMEOUT_MS;
  for (;;) {
    await sleep(POLL_INTERVAL_MS);
    const { data: course } = await apiClient.get<CourseDetail>(
      `/api/documents/courses/${courseId}`,
    );
    if (course.status === "ready") return course;
    if (course.status === "failed") {
      throw new Error("문서 처리에 실패했습니다. 다시 시도해 주세요.");
    }
    if (Date.now() > deadline) {
      throw new Error("문서 처리가 너무 오래 걸립니다. 잠시 후 책장에서 확인해 주세요.");
    }
  }
}
