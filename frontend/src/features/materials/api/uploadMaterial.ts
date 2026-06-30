// [1단계] 백엔드 호출 함수.
// 업로드/문서파싱은 클라우드(Document Parse) 전용이라 runtime provider를 거치지 않고
// apiClient를 직접 사용한다(오프라인 분기 대상 아님).
import { apiClient } from "@/shared/api/client";
import type { MaterialDetail } from "@/features/materials/types";

export async function uploadMaterial(
  file: File,
  title?: string,
): Promise<MaterialDetail> {
  const form = new FormData();
  form.append("file", file);
  if (title) form.append("title", title);

  const { data } = await apiClient.post<MaterialDetail>("/api/materials/upload", form, {
    // 문서 파싱 + 개념 추출 + 임베딩까지 동기 처리 → 넉넉한 타임아웃.
    timeout: 180_000,
  });
  return data;
}
