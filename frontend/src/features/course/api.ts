// 코스 생성 · 진단 · 보강 조달.
//
// ⚠️ 코스 API는 snake_case다(커리큘럼은 camelCase). 어느 쪽으로 맞출지
// 아직 안 정해졌으므로(docs/INTEGRATION.md §3) 응답 모양 그대로 받는다.
// 여기서 임의로 바꾸면 계약이 두 벌이 된다.
//
// **순서가 강제된다.** 진단은 코스가 있어야 돈다 — 선수 판정(16')이 코스
// 소유라서, PPT가 요구하는 선수를 같이 올린 교재가 이미 커버하는지 보려면
// 자료 조합이 정해져 있어야 한다. 그래서 POST /courses가 무조건 먼저다.
import { apiClient } from "@/shared/api/client";

const BASE = "/api/courses";

// ── 코스 ────────────────────────────────────────────────────────

export interface CourseOut {
  id: string;
  user_id: string;
  title: string;
  documents: { document_id: string; role: string; seq: number }[];
  topics: {
    id: string;
    seq: number;
    title: string;
    origin: string;
    plan: string;
  }[];
}

/** 자료들을 한 수업으로 묶는다. **자료가 전부 ready여야 한다** — 서버가 이
 *  자리에서 뼈대의 목차를 복사하고 밀도로 역할을 정하는데, 둘 다 파싱이
 *  끝나야 생기는 값이라 그전에 부르면 목차 0개짜리 코스가 만들어진다. */
export async function createCourse(body: {
  user_id: string;
  document_ids: string[];
  title?: string;
}): Promise<CourseOut> {
  const { data } = await apiClient.post<CourseOut>(BASE, body);
  return data;
}

// ── 진단 ────────────────────────────────────────────────────────

export interface PrereqItem {
  id: string;
  item: string;
  why: string | null;
  status: "pass" | "gray";
  known: string | null;
}

export interface PrereqSubject {
  subject: string;
  ordered: boolean;
  items: PrereqItem[];
}

export interface DiagnosticSetup {
  course_id: string;
  /** 12.5가 판정한 분야. **자동 검증이 없는 값이라 이 화면이 유일한 창구다.** */
  field: string | null;
  documents: string[];
  goal: string | null;
  deadline_weeks: number | null;
  style: string | null;
  diagnosed_at: string | null;
  subjects: PrereqSubject[];
}

/** 진단 화면이 필요한 것 전부. LLM을 안 부르므로 즉시 뜬다. */
export async function fetchSetup(courseId: string): Promise<DiagnosticSetup> {
  const { data } = await apiClient.get<DiagnosticSetup>(
    `${BASE}/${courseId}/diagnostic`,
  );
  return data;
}

export type Style = "metaphor" | "definition" | "table" | "why";

export interface DiagnosticCards {
  concept: string | null;
  /** 생성이 실패하면 빈 객체다. 그때는 이 화면을 건너뛴다. */
  cards: Partial<Record<Style, string>>;
}

/** ② 같은 개념을 네 형식으로. LLM 1콜이라 몇 초 걸린다. */
export async function fetchCards(courseId: string): Promise<DiagnosticCards> {
  const { data } = await apiClient.get<DiagnosticCards>(
    `${BASE}/${courseId}/diagnostic/cards`,
  );
  return data;
}

export type Goal = "exam" | "work" | "interest";

export async function saveConfig(
  courseId: string,
  body: { goal?: Goal; deadline_weeks?: number; style?: Style },
): Promise<DiagnosticSetup> {
  const { data } = await apiClient.patch<DiagnosticSetup>(
    `${BASE}/${courseId}/diagnostic`,
    body,
  );
  return data;
}

export type Known = "known" | "heard" | "unknown";

export interface SubjectAnswersOut {
  /** 펼쳐서 더 물어야 할 과목 — "들어봤다"라고 한 것들. */
  expand: string[];
  setup: DiagnosticSetup;
}

/** ③-1 과목 단위 답. `{과목명: known|heard|unknown}` */
export async function answerSubjects(
  courseId: string,
  answers: Record<string, Known>,
): Promise<SubjectAnswersOut> {
  const { data } = await apiClient.post<SubjectAnswersOut>(
    `${BASE}/${courseId}/diagnostic/subjects`,
    { answers },
  );
  return data;
}

/** ③-2 펼친 과목의 항목별 답. `{prereq_id: known|heard|unknown}` */
export async function answerPrereqs(
  courseId: string,
  answers: Record<string, Known>,
): Promise<DiagnosticSetup> {
  const { data } = await apiClient.post<DiagnosticSetup>(
    `${BASE}/${courseId}/diagnostic/prereqs`,
    { answers },
  );
  return data;
}

export interface Probe {
  prereq_id: string;
  subject: string;
  item: string;
  stem: string;
  choices: string[];
  answer_index: number;
}

/** ④ 확인 문항. **한 번에 다 오지 않는다.**
 *
 *  답을 받아야 다음이 정해지는 구조라(맞히면 한 번 더 묻고, 틀리면 그 과목은
 *  거기서 끝난다) 화면이 **빈 배열이 올 때까지** `GET → POST`를 반복해야 한다.
 *  실측 2라운드 11문항. 라운드마다 LLM을 부르므로 5~15초 걸린다. */
export async function fetchProbes(courseId: string): Promise<Probe[]> {
  const { data } = await apiClient.get<Probe[]>(
    `${BASE}/${courseId}/diagnostic/probes`,
  );
  return data;
}

export interface ProbeGrade {
  graded: number;
  /** 0이면 진단이 끝났다. */
  subjects_left: number;
}

export async function gradeProbes(
  courseId: string,
  results: Record<string, boolean>,
): Promise<ProbeGrade> {
  const { data } = await apiClient.post<ProbeGrade>(
    `${BASE}/${courseId}/diagnostic/probes`,
    { results },
  );
  return data;
}

// ── 26·27 조달 ──────────────────────────────────────────────────

export interface SupplyOut {
  subjects: number;
  made: number;
  reused: number;
  inserted: number;
  updated: number;
}

/** 진단이 "모른다"고 한 과목의 자료를 마련하고 목차 앞에 끼운다.
 *
 *  **여러 번 불러도 안전하다.** 자료는 (분야, 과목) 지문으로 한 번만 만들고,
 *  이미 끼운 단원은 `plan`만 다시 맞춘다. 과목마다 LLM 1콜이라 오래 걸린다. */
export async function supply(courseId: string): Promise<SupplyOut> {
  const { data } = await apiClient.post<SupplyOut>(`${BASE}/${courseId}/supply`);
  return data;
}
