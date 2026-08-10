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
  /** 이번 라운드에 채점된 문항 수. */
  graded: number;
  /** **0이면 진단이 끝났다.** 0이 아니면 다시 GET 해서 다음 라운드를 받는다. */
  subjects_left: number;
}

/** 26·27 — 진단이 "모른다"고 한 과목의 자료를 마련하고 목차 **앞**에 끼운다. */
export interface SupplyResult {
  /** 살펴본 선수 과목 수. */
  subjects: number;
  /** 명세를 새로 쓴 과목 / 이미 있어서 그대로 쓴 과목.
   *  자료는 (분야, 과목) 소유라 두 번째 사람부터는 전부 reused다. */
  made: number;
  reused: number;
  /** 목차에 새로 끼운 단원 / plan만 다시 맞춘 단원. */
  inserted: number;
  updated: number;
}

/** ⑥ 확정 화면 한 줄 — 이 과목을 앞에 넣을지 사용자가 고른다. */
export interface SupplySubject {
  subject: string;
  items: string[];
  why: string | null;
  known: number;
  unknown: number;
  asked: number;
  plan: string;
  /** 체크박스 기본값. 전부 안다고 한 과목은 꺼진 채로 뜬다. */
  selected: boolean;
  /** book: 이 책으로 설명한다 | ready: 만들어 둔 게 있다 | generate: 지금 만든다 */
  source: "book" | "ready" | "generate" | string;
  evidence: {
    document_id: string;
    filename: string;
    concept: string;
    item: string;
    similarity: number;
  } | null;
}

export interface SupplyPreview {
  field: string;
  subjects: SupplySubject[];
  topics_before: number;
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

/** ⑤가 끝나면 부른다. 과목마다 LLM 1콜이라 오래 걸린다(실측 7과목 8콜).
 *
 *  **여러 번 불러도 안전하다.** 자료는 지문으로 한 번만 만들고 이미 끼운
 *  단원은 plan만 다시 맞춘다. 서버가 학습 store까지 다시 조립한다. */
export async function supply(
  courseId: string,
  exclude?: string[],
): Promise<SupplyResult> {
  const { data } = await apiClient.post<SupplyResult>(
    `/api/courses/${courseId}/supply`,
    { exclude: exclude ?? null },
    { timeout: 300000 },
  );
  return data;
}

/** ⑤ 다음, 조달 **전에** 부른다. LLM을 안 쓰므로 1~2초다 —
 *  여기서 만들면 사용자가 뺄 과목까지 만들어 놓고 기다리게 된다. */
export async function previewSupply(courseId: string): Promise<SupplyPreview> {
  const { data } = await apiClient.get<SupplyPreview>(
    `/api/courses/${courseId}/supply/preview`,
    { timeout: 60000 },
  );
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
