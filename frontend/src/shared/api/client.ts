import axios from "axios";

// 일반 API
export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000",
  timeout: 30000,
});

// Solar PDF 파싱·진단·커리큘럼 등 LLM 호출 (30초 초과 가능)
export const llmApiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000",
  timeout: 180000,
});

for (const client of [apiClient, llmApiClient]) {
  client.interceptors.response.use(
    (res) => res,
    (error) => Promise.reject(error),
  );
}
