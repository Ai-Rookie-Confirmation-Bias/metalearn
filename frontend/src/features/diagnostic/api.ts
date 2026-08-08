// 진단(24번) 백엔드 호출.
//
// ⚠️ **코스 API는 snake_case다.** curriculum 쪽(camelCase)과 표기가 갈려 있고
//    아직 통일 전이라, 여기서는 서버가 주는 이름을 그대로 쓴다. 임의로 바꿔
//    담으면 어느 쪽이 진짜인지 화면에서 알 수 없게 된다.
//
// 판단은 전부 백엔드에 있다. 여기서 "안다/모른다"를 해석하거나 순서를 정하지
// 않는다 — ④에서 무엇을 펼칠지도 서버가 `expand`로 돌려준다.
import { apiClient } from "@/shared/api/client";

export type Known = "known" | "heard" | "unknown";
export type Goal = "exam" | "work" | "interest";
export type Style = "metaphor" | "definition" | "table" | "why";

export interface PrereqItem {
  id: string;
  item: string;
  why: string | null;
  status: "pass" | "gray";
  known: Known | null;
}

export interface PrereqSubject {
  subject: string;
  // 하위 항목 사이 순서가 강제되면 보강 '단원', 아니면 한 '꼭지'
  ordered: boolean;
  items: PrereqItem[];
}

export interface DiagnosticSetup {
  course_id: string;
  // 12.5가 판정한 분야. 화면 ②가 이걸 확인받는다 — 자동 검증이 없는 값이라
  // 여기가 유일한 검증 창구다.
  field: string | null;
  documents: string[];
  goal: Goal | null;
  deadline_weeks: number | null;
  style: Style | null;
  diagnosed_at: string | null;
  subjects: PrereqSubject[];
}

export interface DiagnosticCards {
  concept: string | null;
  // metaphor | definition | table | why → 설명 본문. 생성 실패면 빈 객체
  cards: Partial<Record<Style, string>>;
}

export interface Probe {
  prereq_id: string;
  subject: string;
  item: string;
  stem: string;
  choices: string[];
  answer_index: number;
}

export interface ProbeGrade {
  demoted_subjects: string[];
  demoted_items: number;
}

const base = (courseId: string) => `/api/courses/${courseId}/diagnostic`;

export async function fetchSetup(courseId: string): Promise<DiagnosticSetup> {
  // 선수 목록이 아직 없으면 서버가 여기서 계산한다(16'). 첫 호출만 느리다.
  const { data } = await apiClient.get<DiagnosticSetup>(base(courseId), {
    timeout: 180000,
  });
  return data;
}

export async function saveConfig(
  courseId: string,
  body: { goal?: Goal; deadline_weeks?: number | null; style?: Style },
): Promise<DiagnosticSetup> {
  const { data } = await apiClient.patch<DiagnosticSetup>(base(courseId), body);
  return data;
}

export async function fetchCards(courseId: string): Promise<DiagnosticCards> {
  // LLM 1콜.
  const { data } = await apiClient.get<DiagnosticCards>(`${base(courseId)}/cards`, {
    timeout: 120000,
  });
  return data;
}

export async function answerSubjects(
  courseId: string,
  answers: Record<string, Known>,
): Promise<{ expand: string[]; setup: DiagnosticSetup }> {
  const { data } = await apiClient.post(`${base(courseId)}/subjects`, { answers });
  return data;
}

export async function answerPrereqs(
  courseId: string,
  answers: Record<string, Known>,
): Promise<DiagnosticSetup> {
  const { data } = await apiClient.post<DiagnosticSetup>(
    `${base(courseId)}/prereqs`,
    { answers },
  );
  return data;
}

export async function fetchProbes(courseId: string): Promise<Probe[]> {
  // 빈 배열일 수 있다 — 정답을 못 세운 항목은 문항을 안 낸다. 그럼 이 화면을 건너뛴다.
  const { data } = await apiClient.get<Probe[]>(`${base(courseId)}/probes`, {
    timeout: 180000,
  });
  return data;
}

export async function gradeProbes(
  courseId: string,
  results: Record<string, boolean>,
): Promise<ProbeGrade> {
  const { data } = await apiClient.post<ProbeGrade>(`${base(courseId)}/probes`, {
    results,
  });
  return data;
}
