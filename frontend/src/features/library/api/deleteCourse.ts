// DELETE /api/courses/:id — 책장에서 코스 삭제(본인 소유만).
// 콘텐츠·학습 이력까지 전부 지워지고 복구 불가 — 호출 전 확인은 화면 책임.
import { apiClient } from "@/shared/api/client";

export async function deleteCourse(courseId: string): Promise<void> {
  await apiClient.delete(`/api/courses/${courseId}`);
}
