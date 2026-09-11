// 코스 조립 API.
//
// ⚠️ **snake_case다.** diagnostic과 같고 curriculum(camelCase)과 갈려 있다.
//    서버가 주는 이름을 그대로 쓴다.
//
// roles는 보내지 않는다. 서버가 밀도·형식으로 skeleton|body|reference를 정한다.
// 위저드의 메인/추가는 축이 달라서 임의로 짝지으면 사용자가 고르지 않은 값이 저장된다.
import { apiClient } from "@/shared/api/client";

export type MaterialRole = "skeleton" | "body" | "reference";

export interface CourseDocument {
  document_id: string;
  role: MaterialRole | string;
  seq: number;
}

export interface CourseTopic {
  id: string;
  seq: number;
  title: string;
  origin: string;
  plan: string;
  source_topic_id: string | null;
  anchor_concept_id: string | null;
  note: string | null;
}

export interface Course {
  id: string;
  user_id: string;
  title: string;
  /** 진단을 끝냈나. 비어 있으면 책장이 학습 대신 **진단으로** 보낸다. */
  diagnosed_at: string | null;
  documents: CourseDocument[];
  topics: CourseTopic[];
}

export type CreateCourseBody = {
  document_ids: string[];
  title?: string | null;
  // 비우면 서버가 밀도·형식으로 제안한다.
  roles?: Record<string, MaterialRole> | null;
  // 위저드의 자료 유형 최종값 (textbook|slide|notes|exam) — 기출 구분의 진실.
  kinds?: Record<string, string> | null;
};

export async function createCourse(body: CreateCourseBody): Promise<Course> {
  const { data } = await apiClient.post<Course>("/api/courses", body);
  return data;
}

export async function listCourses(): Promise<Course[]> {
  const { data } = await apiClient.get<Course[]>("/api/courses");
  return data;
}

export async function getCourse(courseId: string): Promise<Course> {
  const { data } = await apiClient.get<Course>(`/api/courses/${courseId}`);
  return data;
}

/** 수업을 지운다. **자료 자체는 안 지운다** — 공용이라 남이 같은 책을 쓴다.
 *  대신 그 자료의 책장 연결이 끊겨서, 지운 자리에 PDF가 낱권으로 되살아나지 않는다. */
export async function deleteCourse(courseId: string): Promise<void> {
  await apiClient.delete(`/api/courses/${courseId}`);
}
