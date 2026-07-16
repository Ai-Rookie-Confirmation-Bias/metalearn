// 로컬 엔진 어댑터(:8600) 연동 — 클라우드+로컬 이중구조의 브라우저 쪽 절반.
// 온라인일 때: 절을 열면 어댑터에 오프라인 팩 동기화를 부탁한다(fire-and-forget).
// 오프라인일 때: 채점 요청을 어댑터로 폴백한다(submitAttempt에서 소비).
// 어댑터가 안 떠 있으면 전부 조용히 무시 — 이중구조는 있으면 좋고 없어도 그만.
import axios from "axios";

import { apiBaseUrl } from "@/shared/api/client";

export const LOCAL_ADAPTER_URL = "http://127.0.0.1:8600";

// 어댑터 생존 캐시(15초) — 절 이동마다 헬스핑을 쏘지 않기 위해
let aliveAt = 0;
let alive = false;

export async function isAdapterAlive(): Promise<boolean> {
  if (Date.now() - aliveAt < 15_000) return alive;
  try {
    const { data } = await axios.get(`${LOCAL_ADAPTER_URL}/health`, { timeout: 1200 });
    alive = Boolean(data?.ok);
  } catch {
    alive = false;
  }
  aliveAt = Date.now();
  return alive;
}

/** 온라인일 때 절 팩을 로컬 어댑터에 미리 저장(오프라인 대비). 실패는 무시. */
export async function syncSectionToAdapter(sectionId: string): Promise<void> {
  try {
    if (!(await isAdapterAlive())) return;
    await axios.post(
      `${LOCAL_ADAPTER_URL}/sync`,
      { backendUrl: apiBaseUrl, sectionIds: [sectionId] },
      { timeout: 20_000 },
    );
  } catch {
    // 어댑터 없음/동기화 실패 — 온라인 경로엔 영향 없음
  }
}

/** 오프라인 채점 폴백 — 어댑터의 동일 계약 POST /api/attempts. */
export async function submitAttemptOffline(body: {
  blockId: string;
  conceptId: string;
  kind: string;
  userInput: unknown;
}): Promise<unknown> {
  const { data } = await axios.post(`${LOCAL_ADAPTER_URL}/api/attempts`, body, {
    timeout: 60_000, // 1.2B CPU 채점은 수 초~십수 초
  });
  return data;
}
