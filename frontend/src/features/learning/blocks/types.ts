// 학습 블록 봉투 — README §5 · UXUI_ANT/MetaLearnUXUI.md 명세.
// 모든 콘텐츠(학습·진단·복습·연결)가 같은 봉투를 쓰고, type으로 렌더러를 고른다.
// 새 컴포넌트 = data 타입 + 렌더러 추가뿐 (registry.tsx).

export type ContentSource = "book" | "ai_prereq" | "analogy";
export type AttemptKind = "diagnostic" | "learn" | "review" | "connection"; // attempts.kind

// 블록의 외부 신뢰 근거 (external_refs — ai_prereq 블록의 출처)
export type ExternalRef = { title: string; url?: string; kind: "web" | "corpus" | "prereq_db" };

// 공통 봉투 — README §5 모양 그대로 (blocks 테이블 1:1)
type Envelope<T extends string, D> = {
  id: string;
  type: T;
  conceptId: string;
  kind?: AttemptKind; // 진단/학습/복습/연결 구분 (attempts 기록에 필요)
  source: ContentSource; // 📖 book / 🤖 ai_prereq / 💡 analogy 출처 배지
  sourceChunkIds?: string[]; // book 근거: 책 청크 id ("근거 보기" 기능용)
  externalRefs?: ExternalRef[]; // ai_prereq 근거: 외부 신뢰 출처
  verified: boolean; // 근거 대조 통과(true만 서빙됨)
  tracked: boolean; // ②③ 정답 추적 대상 → 게이트·onAnswer 대상
  meta?: { difficulty?: "low" | "mid" | "high"; version?: number };
  data: D;
};

// ① 설명 — 개념 본문
export type ConceptBlockData = { title?: string; body: string };

// ② 빈칸 — 문장 조각 배열(text/blank 교차). blank는 인라인 input으로 렌더
export type ClozeSegment = { kind: "text"; text: string } | { kind: "blank"; answer: string; aliases?: string[] };
export type ClozeBlockData = { title?: string; segments: ClozeSegment[] };

// ② 객관식
export type McqBlockData = {
  title?: string;
  question: string;
  options: string[];
  answerIndex: number;
  explanation?: string;
};

// ② 파인만 역질문 — 채점은 서버(Solar) rubric 대조. 지금은 mock
export type ExplainBackBlockData = { title?: string; prompt: string; rubric?: string[] };

export type LearningBlock =
  | Envelope<"concept", ConceptBlockData>
  | Envelope<"cloze", ClozeBlockData>
  | Envelope<"mcq", McqBlockData>
  | Envelope<"explainBack", ExplainBackBlockData>;

export type BlockType = LearningBlock["type"];

// ②③ 공통 추적 콜백 — 결과를 위로 방출(페이지가 수집 → 나중에 POST /attempts)
// kind는 블록 컴포넌트가 아니라 registry(BlockRenderer)가 봉투에서 채워줌
export type AnswerEvent = {
  blockId: string;
  conceptId: string;
  kind?: AttemptKind; // POST /attempts 바디의 kind (기본 learn)
  correct: boolean;
  userInput: unknown;
};
export type OnAnswer = (e: AnswerEvent) => void;

// 절 로드 응답 모양 (GET /sections/:id — verified 봉투 배열)
export type SectionPayload = {
  id: string;
  title: string;
  blocks: LearningBlock[];
};
