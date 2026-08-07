// 문제 페이지 타입 정의 + (기출 스타일 시연용) 목데이터.
//
// ⚠️ 08-08부터 화면은 실 API(./api.ts)를 쓴다 — 이 파일의 fetchSession/
// submitAttempt/courseBanks는 화면에서 더 이상 부르지 않는다.
// 남겨두는 이유: ① 타입 정의의 원본(백엔드 스키마와 1:1) ② 기출 스타일 모드
// (QuizStyle="exam")는 백엔드(style 컬럼, QUIZ.md §3.6)가 생기기 전까지
// 이 mock 세트가 유일한 시연 수단.

export type QuizType = "mcq" | "cloze" | "shortAnswer" | "trueFalse";

// 문제 스타일 — standard: 다양한 유형으로 개념 확인 / exam: 기출의 유형 비율·발문 말투 모방
// (기출 문항 복제가 아님 — 내용·정답·근거는 전부 교재 원문에서. docs/QUIZ.md §2-③)
export type QuizStyle = "standard" | "exam";

export type TocSummary = {
  toc_index: number;
  title: string;
  item_count: number;
  // 학습 페이지에서 이 목차를 학습했는지 (section_progress 목차 집계).
  // "어디를 풀지" 안내에만 쓰이고 문항 선정에는 절대 안 쓰임 (§7-③의 선)
  studied?: boolean;
};

export type QuizBankSummary = {
  course_id: string;
  document_id: string;
  tocs: TocSummary[];
  total: number;
};

// 과목(책) 목록 항목 — 책장처럼 과목부터 고르고 들어간다.
// generating = 문제은행 배치가 아직 도는 중(gen_status) → 진입 불가
export type CourseBank = {
  course_id: string;
  title: string;
  category: string;
  status: "ready" | "generating";
  summary: QuizBankSummary | null; // generating이면 null
  // 마지막 학습 시각 (책장과 같은 MAX(attempts.created_at) 계산값) — 추천 배너용
  last_activity_at: string | null;
  // 기출(kind=exam) 문서를 올린 과목만 true → "기출 스타일" 버튼 노출
  has_exam_style: boolean;
};

// 세션 문항 data — 정답·해설이 제거된 모양 (서버 strip_answers 결과와 동일)
export type SessionItemData = {
  question?: string; // mcq
  options?: string[];
  statement?: string; // trueFalse
  prompt?: string; // shortAnswer
  segments?: ({ kind: "text"; text: string } | { kind: "blank" })[]; // cloze
};

export type SessionItem = {
  id: string;
  toc_index: number;
  type: QuizType;
  data: SessionItemData;
};

export type AttemptResponse = {
  correct: boolean;
  answer: {
    answerIndex?: number; // mcq
    answer?: boolean; // trueFalse
    accepted?: string[]; // shortAnswer
    answers?: { answer: string; aliases: string[] }[]; // cloze
    explanation?: string;
  };
  explanation: string | null; // 고른 선지 기준 해설 (오답 mcq일 때)
  evidence: { text: string; pageFrom: number; pageTo: number };
};

// ── 은행 (서버 역할 — 정답 포함 원본. 세션으로는 stripped만 나감) ──

type FullItem = SessionItem & {
  course_id: string;
  style?: QuizStyle; // 생략 = standard
  full: {
    answerIndex?: number;
    answer?: boolean;
    accepted?: string[];
    answers?: { answer: string; aliases: string[] }[];
    explanation: string;
    wrongExplanations?: Record<string, string>;
  };
  evidence: { text: string; pageFrom: number; pageTo: number };
};

const BANK: FullItem[] = [
  // ── 📘 데이터 통신 (crs_datacomm) ──
  {
    id: "q1",
    course_id: "crs_datacomm",
    toc_index: 0,
    type: "mcq",
    data: {
      question: "데이터 통신 시스템의 3요소에 해당하지 않는 것은?",
      options: ["송신자", "수신자", "전송매체", "프로토콜"],
    },
    full: {
      answerIndex: 3,
      explanation: "데이터 통신 시스템은 송신자, 수신자, 전송 매체의 세 요소로 구성됩니다.",
      wrongExplanations: {
        "0": "송신자는 데이터를 보내는 주체로 3요소에 포함됩니다.",
        "1": "수신자는 데이터를 받는 주체로 3요소에 포함됩니다.",
        "2": "전송매체는 데이터가 지나가는 통로로 3요소에 포함됩니다.",
      },
    },
    evidence: {
      text: "데이터 통신 시스템은 송신자, 수신자, 전송 매체의 세 요소로 구성된다.",
      pageFrom: 12,
      pageTo: 12,
    },
  },
  {
    id: "q2",
    course_id: "crs_datacomm",
    toc_index: 0,
    type: "shortAnswer",
    data: { prompt: "데이터가 한 방향으로만 전송되는 통신 방식은?" },
    full: {
      accepted: ["단방향 통신", "단방향", "심플렉스", "Simplex"],
      explanation: "단방향(Simplex) 통신은 라디오·TV 방송처럼 한쪽으로만 데이터가 흐릅니다.",
    },
    evidence: {
      text: "단방향(Simplex) 통신은 데이터가 한 방향으로만 전송되는 방식으로, 라디오와 TV 방송이 대표적이다.",
      pageFrom: 14,
      pageTo: 14,
    },
  },
  {
    id: "q3",
    course_id: "crs_datacomm",
    toc_index: 0,
    type: "trueFalse",
    data: { statement: "반이중(Half-Duplex) 통신은 양쪽이 동시에 데이터를 보낼 수 있다." },
    full: {
      answer: false,
      explanation: "반이중은 양방향이지만 한 번에 한쪽만 전송할 수 있습니다(무전기). 동시 양방향은 전이중(Full-Duplex)입니다.",
    },
    evidence: {
      text: "반이중(Half-Duplex) 통신은 양방향 전송이 가능하지만 동시에는 불가능하며, 무전기가 대표적인 예이다.",
      pageFrom: 14,
      pageTo: 15,
    },
  },
  {
    id: "q4",
    course_id: "crs_datacomm",
    toc_index: 1,
    type: "mcq",
    data: {
      question: "OSI 7계층에서 종단 간 신뢰성 있는 데이터 전송을 담당하는 계층은?",
      options: ["네트워크 계층", "전송 계층", "세션 계층", "데이터링크 계층"],
    },
    full: {
      answerIndex: 1,
      explanation: "전송 계층은 종단 시스템 간 신뢰성 있는 데이터 전송을 보장하며 흐름 제어와 오류 제어를 담당합니다.",
      wrongExplanations: {
        "0": "네트워크 계층은 경로 설정(라우팅)을 담당합니다.",
        "2": "세션 계층은 통신 세션의 수립·유지·종료를 담당합니다.",
        "3": "데이터링크 계층은 인접 노드 간 전송을 담당합니다.",
      },
    },
    evidence: {
      text: "전송 계층은 종단 시스템 간의 신뢰성 있는 데이터 전송을 보장하며, 흐름 제어와 오류 제어를 담당한다.",
      pageFrom: 74,
      pageTo: 74,
    },
  },
  {
    id: "q5",
    course_id: "crs_datacomm",
    toc_index: 1,
    type: "cloze",
    data: {
      segments: [
        { kind: "text", text: "OSI 7계층의 최하위 계층은 " },
        { kind: "blank" },
        { kind: "text", text: " 계층으로, 비트 단위의 전송을 담당한다." },
      ],
    },
    full: {
      answers: [{ answer: "물리", aliases: ["물리 계층", "Physical"] }],
      explanation: "물리 계층은 실제 전기 신호(비트)를 전송 매체로 보내는 최하위 계층입니다.",
    },
    evidence: {
      text: "물리 계층은 OSI 7계층의 최하위 계층으로, 비트 단위의 데이터를 전기 신호로 변환하여 전송한다.",
      pageFrom: 68,
      pageTo: 68,
    },
  },
  {
    id: "q6",
    course_id: "crs_datacomm",
    toc_index: 1,
    type: "shortAnswer",
    data: { prompt: "OSI 7계층에서 데이터의 표현 형식 변환(암호화·압축)을 담당하는 계층은?" },
    full: {
      accepted: ["표현 계층", "표현", "프레젠테이션 계층", "Presentation"],
      explanation: "표현 계층은 데이터의 형식 변환, 암호화, 압축을 담당합니다.",
    },
    evidence: {
      text: "표현 계층(Presentation Layer)은 데이터의 표현 형식을 변환하며 암호화와 압축을 담당한다.",
      pageFrom: 71,
      pageTo: 71,
    },
  },
  {
    id: "q7",
    course_id: "crs_datacomm",
    toc_index: 2,
    type: "mcq",
    data: {
      question: "신호가 전송 매체를 지나며 세기가 약해지는 현상은?",
      options: ["감쇠", "왜곡", "잡음", "지연"],
    },
    full: {
      answerIndex: 0,
      explanation: "감쇠(Attenuation)는 거리가 멀어질수록 신호의 세기가 약해지는 현상입니다.",
      wrongExplanations: {
        "1": "왜곡은 신호의 모양이 변형되는 현상입니다.",
        "2": "잡음은 원치 않는 신호가 섞이는 현상입니다.",
        "3": "지연은 신호 도착이 늦어지는 현상입니다.",
      },
    },
    evidence: {
      text: "감쇠는 신호가 전송 매체를 통과하면서 거리에 따라 세기가 약해지는 현상이다.",
      pageFrom: 96,
      pageTo: 96,
    },
  },
  {
    id: "q8",
    course_id: "crs_datacomm",
    toc_index: 2,
    type: "trueFalse",
    data: { statement: "열잡음은 전자의 불규칙한 운동으로 발생하며 완전히 제거할 수 없다." },
    full: {
      answer: true,
      explanation: "열잡음(백색잡음)은 도체 내 전자의 열운동으로 발생해 온도가 있는 한 제거가 불가능합니다.",
    },
    evidence: {
      text: "열잡음은 전자의 불규칙한 열운동에 의해 발생하는 잡음으로, 완전한 제거가 불가능하다.",
      pageFrom: 98,
      pageTo: 98,
    },
  },
  {
    id: "q9",
    course_id: "crs_datacomm",
    toc_index: 3,
    type: "shortAnswer",
    data: { prompt: "미국 전기전자 기술자 협회로, LAN 표준(802 시리즈)을 제정한 기구는?" },
    full: {
      accepted: ["IEEE", "전기전자기술자협회"],
      explanation: "IEEE는 LAN/MAN 표준인 802 시리즈(이더넷 802.3, 무선랜 802.11 등)를 제정했습니다.",
    },
    evidence: {
      text: "IEEE(미국 전기전자 기술자 협회)는 LAN 표준인 802 시리즈를 제정하였다.",
      pageFrom: 121,
      pageTo: 121,
    },
  },
  {
    id: "q10",
    course_id: "crs_datacomm",
    toc_index: 3,
    type: "mcq",
    data: {
      question: "국제 표준화 기구로, OSI 참조모델을 제정한 곳은?",
      options: ["ISO", "ITU-T", "ANSI", "EIA"],
    },
    full: {
      answerIndex: 0,
      explanation: "ISO(국제표준화기구)가 OSI 7계층 참조모델을 제정했습니다.",
      wrongExplanations: {
        "1": "ITU-T는 전기통신 분야 표준(X.25 등)을 담당합니다.",
        "2": "ANSI는 미국 국가 표준 기구입니다.",
        "3": "EIA는 미국 전자산업협회로 RS-232C 등을 제정했습니다.",
      },
    },
    evidence: {
      text: "ISO는 국제 표준화 기구로서 개방형 시스템 상호연결(OSI) 참조모델을 제정하였다.",
      pageFrom: 119,
      pageTo: 119,
    },
  },
  // ── 📘 데이터 통신 — 기출 스타일 세트 (실기 단답형 말투 모방, 내용은 교재 원문) ──
  {
    id: "e1",
    course_id: "crs_datacomm",
    style: "exam",
    toc_index: 0,
    type: "shortAnswer",
    data: {
      prompt: "다음 설명에 해당하는 통신 방식을 쓰시오: 양방향 전송이 가능하지만 동시에는 불가능하며, 무전기가 대표적인 예이다.",
    },
    full: {
      accepted: ["반이중", "반이중 통신", "Half-Duplex", "하프 듀플렉스"],
      explanation: "반이중(Half-Duplex) 통신입니다. 동시 양방향은 전이중(Full-Duplex)입니다.",
    },
    evidence: {
      text: "반이중(Half-Duplex) 통신은 양방향 전송이 가능하지만 동시에는 불가능하며, 무전기가 대표적인 예이다.",
      pageFrom: 14,
      pageTo: 15,
    },
  },
  {
    id: "e2",
    course_id: "crs_datacomm",
    style: "exam",
    toc_index: 1,
    type: "shortAnswer",
    data: {
      prompt: "다음 설명에 해당하는 OSI 계층을 쓰시오: 종단 시스템 간의 신뢰성 있는 데이터 전송을 보장하며, 흐름 제어와 오류 제어를 담당한다.",
    },
    full: {
      accepted: ["전송 계층", "전송", "Transport Layer", "트랜스포트 계층"],
      explanation: "전송 계층(Transport Layer)입니다. TCP가 대표적인 전송 계층 프로토콜입니다.",
    },
    evidence: {
      text: "전송 계층은 종단 시스템 간의 신뢰성 있는 데이터 전송을 보장하며, 흐름 제어와 오류 제어를 담당한다.",
      pageFrom: 74,
      pageTo: 74,
    },
  },
  {
    id: "e3",
    course_id: "crs_datacomm",
    style: "exam",
    toc_index: 1,
    type: "shortAnswer",
    data: {
      prompt: "다음 설명에 해당하는 계층을 쓰시오: 데이터의 표현 형식을 변환하며 암호화와 압축을 담당한다.",
    },
    full: {
      accepted: ["표현 계층", "표현", "프레젠테이션 계층", "Presentation"],
      explanation: "표현 계층(Presentation Layer)입니다.",
    },
    evidence: {
      text: "표현 계층(Presentation Layer)은 데이터의 표현 형식을 변환하며 암호화와 압축을 담당한다.",
      pageFrom: 71,
      pageTo: 71,
    },
  },
  {
    id: "e4",
    course_id: "crs_datacomm",
    style: "exam",
    toc_index: 2,
    type: "shortAnswer",
    data: {
      prompt: "다음 설명에 해당하는 현상을 쓰시오: 신호가 전송 매체를 통과하면서 거리에 따라 세기가 약해진다.",
    },
    full: {
      accepted: ["감쇠", "감쇄", "Attenuation"],
      explanation: "감쇠(Attenuation)입니다. 이를 보완하기 위해 증폭기·리피터를 사용합니다.",
    },
    evidence: {
      text: "감쇠는 신호가 전송 매체를 통과하면서 거리에 따라 세기가 약해지는 현상이다.",
      pageFrom: 96,
      pageTo: 96,
    },
  },
  {
    id: "e5",
    course_id: "crs_datacomm",
    style: "exam",
    toc_index: 3,
    type: "shortAnswer",
    data: {
      prompt: "다음 설명에 해당하는 표준화 기구를 쓰시오: LAN 표준인 802 시리즈를 제정한 미국 전기전자 기술자 협회이다.",
    },
    full: {
      accepted: ["IEEE", "전기전자기술자협회"],
      explanation: "IEEE입니다. 이더넷(802.3), 무선랜(802.11) 표준이 대표적입니다.",
    },
    evidence: {
      text: "IEEE(미국 전기전자 기술자 협회)는 LAN 표준인 802 시리즈를 제정하였다.",
      pageFrom: 121,
      pageTo: 121,
    },
  },
  // ── 📗 알고리즘 (crs_algo) ──
  {
    id: "a1",
    course_id: "crs_algo",
    toc_index: 0,
    type: "mcq",
    data: {
      question: "평균 시간 복잡도가 O(n log n)이 아닌 정렬 알고리즘은?",
      options: ["퀵 정렬", "병합 정렬", "힙 정렬", "버블 정렬"],
    },
    full: {
      answerIndex: 3,
      explanation: "버블 정렬은 인접 원소를 반복 비교·교환하는 방식으로 평균 O(n²)입니다.",
      wrongExplanations: {
        "0": "퀵 정렬의 평균 시간 복잡도는 O(n log n)입니다.",
        "1": "병합 정렬은 항상 O(n log n)입니다.",
        "2": "힙 정렬은 항상 O(n log n)입니다.",
      },
    },
    evidence: {
      text: "버블 정렬은 인접한 두 원소를 비교하여 교환하는 정렬로, 평균 시간 복잡도는 O(n²)이다.",
      pageFrom: 42,
      pageTo: 42,
    },
  },
  {
    id: "a2",
    course_id: "crs_algo",
    toc_index: 0,
    type: "shortAnswer",
    data: { prompt: "이미 정렬된 부분에 새 원소를 알맞은 위치에 끼워 넣는 정렬 알고리즘은?" },
    full: {
      accepted: ["삽입 정렬", "삽입정렬", "Insertion Sort"],
      explanation: "삽입 정렬은 앞쪽의 정렬된 구간에 새 원소를 끼워 넣으며, 거의 정렬된 데이터에 특히 빠릅니다.",
    },
    evidence: {
      text: "삽입 정렬은 정렬된 부분에 새로운 원소를 적절한 위치에 삽입하는 방식으로 동작한다.",
      pageFrom: 38,
      pageTo: 38,
    },
  },
  {
    id: "a3",
    course_id: "crs_algo",
    toc_index: 1,
    type: "trueFalse",
    data: { statement: "깊이 우선 탐색(DFS)은 큐(Queue)를 사용하여 구현한다." },
    full: {
      answer: false,
      explanation: "DFS는 스택(또는 재귀)으로 구현합니다. 큐를 쓰는 것은 너비 우선 탐색(BFS)입니다.",
    },
    evidence: {
      text: "깊이 우선 탐색은 스택을 이용하여 구현하며, 너비 우선 탐색은 큐를 이용한다.",
      pageFrom: 87,
      pageTo: 87,
    },
  },
  {
    id: "a4",
    course_id: "crs_algo",
    toc_index: 1,
    type: "cloze",
    data: {
      segments: [
        { kind: "text", text: "다익스트라 알고리즘은 " },
        { kind: "blank" },
        { kind: "text", text: " 가중치 간선이 있는 그래프에서는 사용할 수 없다." },
      ],
    },
    full: {
      answers: [{ answer: "음수", aliases: ["음의", "음"] }],
      explanation: "다익스트라는 음수 가중치가 있으면 최단 경로를 보장하지 못합니다. 이때는 벨만-포드를 사용합니다.",
    },
    evidence: {
      text: "다익스트라 알고리즘은 음수 가중치 간선이 존재하는 그래프에서는 올바른 최단 경로를 구할 수 없다.",
      pageFrom: 95,
      pageTo: 95,
    },
  },
];

// ── 과목(책) 목록 — GET /courses + 각 코스의 quiz 요약을 합친 모양 ──
// 문항 수는 확정안 예시 수치 (실제로는 quiz_items 집계값)

export const courseBanks: CourseBank[] = [
  {
    course_id: "crs_datacomm",
    title: "데이터 통신",
    category: "Computer Science",
    status: "ready",
    last_activity_at: "2026-08-01T10:00:00Z",
    has_exam_style: true, // 기출_23-25.pdf를 올린 과목 → 기출 스타일 모드 존재
    summary: {
      course_id: "crs_datacomm",
      document_id: "doc_1",
      tocs: [
        { toc_index: 0, title: "1. 데이터 통신 개요", item_count: 31, studied: true },
        { toc_index: 1, title: "2. OSI 참조모델", item_count: 37, studied: true },
        { toc_index: 2, title: "3. 신호와 잡음", item_count: 26 },
        { toc_index: 3, title: "4. 표준화 기구", item_count: 34 },
      ],
      total: 128,
    },
  },
  {
    course_id: "crs_algo",
    title: "알고리즘적 사고와 문제해결력",
    category: "Computer Science",
    status: "ready",
    last_activity_at: "2026-08-05T21:30:00Z", // 가장 최근 → 추천 배너 대상
    has_exam_style: false, // 교재만 올림 → 일반 모드만
    summary: {
      course_id: "crs_algo",
      document_id: "doc_2",
      tocs: [
        { toc_index: 0, title: "1. 정렬 알고리즘", item_count: 24, studied: true },
        { toc_index: 1, title: "2. 그래프 탐색", item_count: 18 },
      ],
      total: 42,
    },
  },
  {
    course_id: "crs_os",
    title: "운영체제",
    category: "Computer Science",
    status: "generating", // 파싱 직후 문제은행 배치가 도는 중 — 진입 불가
    summary: null,
    last_activity_at: null,
    has_exam_style: false,
  },
];

const delay = (ms: number) => new Promise((r) => setTimeout(r, ms));
const norm = (s: string) => s.replace(/\s+/g, "").toLowerCase();

// POST /courses/:id/quiz/session 대역 — 과목·범위·스타일 내 무작위 샘플, 정답 제거
export async function fetchSession(
  courseId: string,
  tocIndexes: number[],
  count: number,
  style: QuizStyle = "standard",
): Promise<SessionItem[]> {
  await delay(250);
  const pool = BANK.filter(
    (it) =>
      it.course_id === courseId &&
      tocIndexes.includes(it.toc_index) &&
      (it.style ?? "standard") === style,
  );
  const shuffled = [...pool].sort(() => Math.random() - 0.5).slice(0, count);
  return shuffled.map(({ id, toc_index, type, data }) => ({ id, toc_index, type, data }));
}

// POST /quiz/attempts 대역 — 서버 채점 규칙(공백 정규화·별칭·O/X)과 동일
export async function submitAttempt(
  itemId: string,
  userInput: number | boolean | string | string[],
): Promise<AttemptResponse> {
  await delay(250);
  const item = BANK.find((it) => it.id === itemId);
  if (!item) throw new Error("quiz item not found");
  const f = item.full;

  let correct = false;
  if (item.type === "mcq") {
    correct = Number(userInput) === f.answerIndex;
  } else if (item.type === "trueFalse") {
    correct = userInput === f.answer;
  } else if (item.type === "shortAnswer") {
    correct = (f.accepted ?? []).some((a) => norm(a) === norm(String(userInput)));
  } else if (item.type === "cloze") {
    const given = Array.isArray(userInput) ? userInput : [String(userInput)];
    correct =
      given.length === (f.answers ?? []).length &&
      (f.answers ?? []).every((blank, i) =>
        [blank.answer, ...blank.aliases].some((a) => norm(a) === norm(given[i] ?? "")),
      );
  }

  // 오답 mcq면 "고른 선지" 기준 해설 (확정안 §6-2 "④를 고르셨네요")
  const chosen =
    !correct && item.type === "mcq" ? f.wrongExplanations?.[String(userInput)] ?? null : null;

  return {
    correct,
    answer: {
      answerIndex: f.answerIndex,
      answer: f.answer,
      accepted: f.accepted,
      answers: f.answers,
      explanation: f.explanation,
    },
    explanation: chosen,
    evidence: item.evidence,
  };
}
