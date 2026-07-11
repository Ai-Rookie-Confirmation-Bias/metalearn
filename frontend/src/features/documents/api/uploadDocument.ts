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

/** 비동기 ingest 완료까지 course status를 폴링해 완성된 CourseDetail을 반환. */
async function pollCourseReady(courseId: string): Promise<CourseDetail> {
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

/**
 * 단일 PDF 업로드. 비동기 ingest(ISSUE-010②)라 접수 후 상태를 폴링해
 * 완성된 CourseDetail을 반환한다(호출부 계약은 동기 업로드와 동일).
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
  return pollCourseReady(accepted.course_id ?? accepted.id);
}

export interface BatchFile {
  file: File;
  role: "primary" | "supplementary";
}

/**
 * 다중 PDF 업로드 — 여러 PDF를 순서대로 하나의 코스로 통합(1:N).
 * files 배열 순서 = 학습 순서(primary 척추). supplementary는 RAG 근거로만.
 * links = 보조 링크 URL — 서버가 fetch해 청크·임베딩만 남긴다(RAG 근거).
 * 서버가 문서들을 순서대로 ingest하고 트리를 한 번에 만든 뒤 ready가 된다.
 */
export async function uploadDocumentBatch(
  files: BatchFile[],
  title?: string,
  links: string[] = [],
): Promise<CourseDetail> {
  const form = new FormData();
  for (const f of files) {
    form.append("files", f.file);
    form.append("roles", f.role);
  }
  for (const url of links) form.append("links", url);
  if (title) form.append("title", title);

  const { data: accepted } = await apiClient.post<UploadAccepted>(
    "/api/documents/upload-batch",
    form,
    { headers: { "Content-Type": "multipart/form-data" }, timeout: 60_000 },
  );
  return pollCourseReady(accepted.course_id ?? accepted.id);
}
