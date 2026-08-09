// 문제 페이지 자기 풀이 기록 — localStorage.
//
// 학습 페이지 데이터가 아니라 문제 페이지 안에서 생긴 기록이므로 격리
// 원칙(docs/QUIZ.md §7-③)과 무관하다. 서버는 이 기록을 저장하지 않고,
// 세션 요청의 exclude_ids로만 받아 "안 푼 문제 우선" 샘플링에 쓴다.
//
// 배열 순서 = 푼 지 오래된 순 (맨 뒤가 최근). 서버 계약과 같은 순서라
// 그대로 exclude_ids로 보내면 복습 채움도 오래된 것부터 나온다.

export type SolvedEntry = { id: string; toc: number };

// 서버 SessionRequest.exclude_ids의 max_length와 동일 — 넘치면 오래된 것부터 버림
const CAP = 2000;

const key = (courseId: string, documentId: string) =>
  `quiz.solved.${courseId}.${documentId}`;

export function loadSolved(courseId: string, documentId: string): SolvedEntry[] {
  try {
    const raw = localStorage.getItem(key(courseId, documentId));
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(
      (e): e is SolvedEntry =>
        typeof e === "object" && e !== null &&
        typeof (e as SolvedEntry).id === "string" &&
        typeof (e as SolvedEntry).toc === "number",
    );
  } catch {
    return []; // 손상된 기록은 없는 셈 친다 — 최악이 "복습이 좀 일찍 나옴"뿐
  }
}

// 채점이 끝난 문항을 기록한다. 이미 있으면 맨 뒤로(방금 푼 것) 옮긴다.
export function recordSolved(
  courseId: string,
  documentId: string,
  id: string,
  toc: number,
): void {
  try {
    const entries = loadSolved(courseId, documentId).filter((e) => e.id !== id);
    entries.push({ id, toc });
    localStorage.setItem(
      key(courseId, documentId),
      JSON.stringify(entries.slice(-CAP)),
    );
  } catch {
    // 저장 실패(용량 등)는 무시 — 풀이 진행을 막을 이유가 없다
  }
}

// 목차별 푼 문항 수 — 범위 선택 화면의 "안 푼 N" 표시용
export function solvedCountByToc(entries: SolvedEntry[]): Record<number, number> {
  const acc: Record<number, number> = {};
  for (const e of entries) acc[e.toc] = (acc[e.toc] ?? 0) + 1;
  return acc;
}
