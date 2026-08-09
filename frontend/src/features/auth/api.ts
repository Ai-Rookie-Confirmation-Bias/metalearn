import { apiClient, apiBaseUrl, clearToken } from "@/shared/api/client";

export type Provider = "google" | "naver";

export interface Me {
  id: string;
  email: string;
  name: string | null;
  provider: string;
}

/**
 * 제공자 로그인 시작 — 브라우저 **전체**를 백엔드로 보낸다.
 *
 * fetch로 부르면 안 된다. 백엔드가 제공자 동의화면으로 302를 주는데,
 * 그 페이지는 사람이 직접 봐야 한다.
 */
export function startLogin(provider: Provider): void {
  window.location.href = `${apiBaseUrl}/api/auth/login/${provider}`;
}

/** 지금 요청이 누구 것인가. 미로그인이면 dev 유저가 온다(에러가 아니다). */
export async function fetchMe(): Promise<Me> {
  const { data } = await apiClient.get<Me>("/api/auth/me");
  return data;
}

/** 제공자별 구성 여부 { google, naver } — 미설정 버튼을 잠그는 근거. */
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
