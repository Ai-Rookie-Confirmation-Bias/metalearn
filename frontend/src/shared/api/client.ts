import axios from "axios";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
// 백엔드 core/deps.py의 DEV_USER_ID와 같은 값이어야 한다.
const DEV_USER_ID =
  import.meta.env.VITE_DEV_USER_ID ?? "00000000-0000-0000-0000-000000000001";

// ── 인증 토큰(로컬 스토리지) ──────────────────────────────────────
// OAuth 로그인 성공 시 받은 JWT를 저장한다. 있으면 Authorization Bearer로
// 보내고(정식 경로), 없으면 dev 고정 유저 헤더로 폴백한다 —
// **로그인하지 않아도 지금까지처럼 전부 돈다.**
const TOKEN_KEY = "ml_access_token";

export const getToken = (): string | null => localStorage.getItem(TOKEN_KEY);
export const setToken = (t: string): void => localStorage.setItem(TOKEN_KEY, t);
export const clearToken = (): void => localStorage.removeItem(TOKEN_KEY);
export const isLoggedIn = (): boolean => getToken() !== null;

export const apiBaseUrl = API_BASE;

// 공통 Axios 인스턴스. 오래 걸리는 호출은 호출부에서 timeout을 따로 준다
// (업로드 120초 등) — 느린 API마다 인스턴스를 늘리지 않는다.
export const apiClient = axios.create({
  baseURL: API_BASE,
  timeout: 30000,
});

apiClient.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers.set("Authorization", `Bearer ${token}`);
    config.headers.delete("X-User-Id");
  } else {
    config.headers.set("X-User-Id", DEV_USER_ID);
  }
  return config;
});

apiClient.interceptors.response.use(
  (res) => res,
  (error) => {
    // 토큰이 만료·무효면 들고 있어도 계속 401이다. 비우면 다음 요청부터
    // dev 폴백으로 내려가 화면이 멈추지 않는다.
    if (error?.response?.status === 401) clearToken();
    return Promise.reject(error);
  },
);
