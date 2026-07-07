// API 에러에서 사람이 읽을 수 있는 메시지를 추출.
// FastAPI는 보통 { detail: "..." } 형태로 사유를 준다 → 그걸 우선 노출.
import axios from "axios";

export function apiErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === "string") return detail;
    if (detail) return JSON.stringify(detail);
    return error.message;
  }
  return error instanceof Error ? error.message : String(error);
}
