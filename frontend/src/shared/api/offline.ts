// 로컬 엔진 어댑터(:8600) 연동 — 클라우드+로컬 이중구조의 브라우저 쪽 절반.
// 온라인일 때: 절을 열면 어댑터에 오프라인 팩 동기화를 부탁한다(fire-and-forget).
// 오프라인일 때: 채점 요청을 어댑터로 폴백한다(submitAttempt에서 소비).
// 어댑터가 안 떠 있으면 전부 조용히 무시 — 이중구조는 있으면 좋고 없어도 그만.
import axios from "axios";

import { apiBaseUrl } from "@/shared/api/client";

export const LOCAL_ADAPTER_URL = "http://127.0.0.1:8600";

// ── 오프라인 시도 재생 큐 (Phase 2 재동기화) ─────────────────────────────────
// 오프라인 채점은 즉시 형성 피드백일 뿐, 서버 기록이 아니다. 온라인 복귀 시
// 여기 쌓인 userInput을 그대로 POST /attempts로 재전송하면 서버가 **정식 재채점**
// 하고 BKT·복습 스케줄·진행을 반영한다(서버가 채점의 진실 — 오프라인 판정은 미신뢰).
const REPLAY_KEY = "ml_offline_attempts";

export type OfflineAttempt = {
  blockId: string;
  conceptId: string;
  kind: string;
  userInput: unknown;
  ts: number;
};

function readQueue(): OfflineAttempt[] {
  try {
    const raw = localStorage.getItem(REPLAY_KEY);
    return raw ? (JSON.parse(raw) as OfflineAttempt[]) : [];
  } catch {
    return [];
  }
}

function writeQueue(q: OfflineAttempt[]): void {
  try {
    localStorage.setItem(REPLAY_KEY, JSON.stringify(q));
  } catch {
    // 스토리지 불가(사생활 모드 등) — 재생 포기, 오프라인 피드백은 이미 줬음
  }
}

export function queueOfflineAttempt(a: Omit<OfflineAttempt, "ts">): void {
  writeQueue([...readQueue(), { ...a, ts: Date.now() }]);
}

export function pendingReplayCount(): number {
  return readQueue().length;
}

/** 온라인 복귀 시 큐를 서버로 flush(정식 재채점). 반환: 재동기화된 시도 수.
 *  poster는 실제 온라인 제출 함수(submitAttempt의 온라인 경로만) — 순환 import 회피 주입. */
export async function replayOfflineAttempts(
  poster: (body: { blockId: string; conceptId: string; kind: string; userInput: unknown }) => Promise<unknown>,
): Promise<number> {
  const q = readQueue();
  if (q.length === 0) return 0;
  const remaining: OfflineAttempt[] = [];
  let synced = 0;
  // 시간순 처리 — BKT는 순서 의존(먼저 틀리고 나중에 맞음이 의미 있음)
  for (const a of q.sort((x, y) => x.ts - y.ts)) {
    try {
      await poster({ blockId: a.blockId, conceptId: a.conceptId, kind: a.kind, userInput: a.userInput });
      synced += 1;
    } catch {
      remaining.push(a); // 아직 서버 안 닿음 → 큐에 남겨 다음 기회에
    }
  }
  writeQueue(remaining);
  return synced;
}

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

/** 온라인일 때 절 팩(들)을 로컬 어댑터에 미리 저장(오프라인 대비). 실패는 무시.
 *  현재 절 + 다음 절을 함께 프리페치 — 오프라인 진입 후 다음 절까지 이어 풀 수 있게. */
export async function syncSectionToAdapter(...sectionIds: (string | null | undefined)[]): Promise<void> {
  const ids = sectionIds.filter((s): s is string => Boolean(s));
  if (ids.length === 0) return;
  try {
    if (!(await isAdapterAlive())) return;
    await axios.post(
      `${LOCAL_ADAPTER_URL}/sync`,
      { backendUrl: apiBaseUrl, sectionIds: ids },
      { timeout: 30_000 },
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
