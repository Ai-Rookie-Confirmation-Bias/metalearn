import axios from "axios";

// 공통 Axios 인스턴스 + 에러 인터셉터
export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000",
  timeout: 30000,
});

apiClient.interceptors.response.use(
  (res) => res,
  (error) => {
    // TODO: 전역 에러 처리 (토스트/로깅 등)
    return Promise.reject(error);
  },
);
