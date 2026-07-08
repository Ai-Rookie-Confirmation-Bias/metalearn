import axios from "axios";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
const DEV_USER_ID =
  import.meta.env.VITE_DEV_USER_ID ?? "00000000-0000-0000-0000-000000000001";

// ── 인증 토큰(로컬 스토리지) ──────────────────────────────────────
// OAuth 로그인 성공 시 발급된 JWT를 저장/소비한다. 있으면 Authorization
// Bearer로 보내고(정식 경로), 없으면 dev 고정 유저 헤더로 폴백(하위호환).
const TOKEN_KEY = "ml_access_token";

export const getToken = (): string | null => localStorage.getItem(TOKEN_KEY);
export const setToken = (t: string): void => localStorage.setItem(TOKEN_KEY, t);
export const clearToken = (): void => localStorage.removeItem(TOKEN_KEY);
export const isLoggedIn = (): boolean => getToken() !== null;

export const apiBaseUrl = API_BASE;

// 일반 API
export const apiClient = axios.create({ baseURL: API_BASE, timeout: 30000 });

// Solar PDF 파싱·진단·커리큘럼 등 LLM 호출 (30초 초과 가능)
export const llmApiClient = axios.create({ baseURL: API_BASE, timeout: 180000 });

for (const client of [apiClient, llmApiClient]) {
  // 매 요청마다 인증 헤더 결정: 로그인 상태면 Bearer, 아니면 dev 유저.
  client.interceptors.request.use((config) => {
    const token = getToken();
    if (token) {
      config.headers.set("Authorization", `Bearer ${token}`);
      config.headers.delete("X-User-Id");
    } else {
      config.headers.set("X-User-Id", DEV_USER_ID);
    }
    return config;
  });
  client.interceptors.response.use(
    (res) => res,
    (error) => {
      // 토큰 만료/무효 → 로컬 토큰 정리(다음 요청은 dev 폴백 또는 재로그인 유도).
      if (error?.response?.status === 401) clearToken();
      return Promise.reject(error);
    },
  );
}
