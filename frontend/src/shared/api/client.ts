import axios from "axios";

// 공통 Axios 인스턴스 + 에러 인터셉터
export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000",
  timeout: 30000,
  headers: {
    // 임시 인증(ISSUE-005): OAuth 붙기 전까지 dev 고정 유저. 시드 DEV_USER_ID와 일치.
    "X-User-Id":
      import.meta.env.VITE_DEV_USER_ID ?? "00000000-0000-0000-0000-000000000001",
  },
});

apiClient.interceptors.response.use(
  (res) => res,
  (error) => {
    // TODO: 전역 에러 처리 (토스트/로깅 등)
    return Promise.reject(error);
  },
);
