import { apiClient, apiBaseUrl, clearToken } from "@/shared/api/client";

export type Provider = "google" | "naver";

export interface Me {
  id: string;
  email: string;
  name: string | null;
  provider: string;
}

/** 제공자 로그인 시작 — 백엔드 로그인 엔드포인트로 브라우저 전체를 리다이렉트한다.
 * 백엔드가 제공자 동의화면으로 302, 콜백에서 다시 프론트 /auth/callback으로 302. */
export function startLogin(provider: Provider): void {
  window.location.href = `${apiBaseUrl}/api/auth/login/${provider}`;
}

/** 현재 로그인 사용자. 미로그인(dev 폴백)이면 dev 유저가 온다. */
export async function fetchMe(): Promise<Me> {
  const { data } = await apiClient.get<Me>("/api/auth/me");
  return data;
}

/** 제공자별 구성 여부 { google: bool, naver: bool } — 버튼 활성화 판단용. */
export async function fetchProviders(): Promise<Record<string, boolean>> {
  const { data } = await apiClient.get<Record<string, boolean>>(
    "/api/auth/providers",
  );
  return data;
}

export function logout(): void {
  clearToken();
  localStorage.removeItem("ml_last_provider");
}
