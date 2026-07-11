// 학습 화면 mock — 단일 소스. 화면의 모든 것(진도율·잠금·현재 절·블록)은 여기서 파생된다.
// 실제 응답 모양 그대로: 코스 트리 = GET /courses/:id, 절 블록 = GET /sections/:id(실제론 지연 로드),
// 완료 상태 = section_progress. 백엔드 붙으면 값만 fetch로 교체.
// 검증 규칙(SCHEMA.md): verified=true 이려면 book→sourceChunkIds, ai_prereq→externalRefs 비어있지 않아야.
import type { SectionPayload } from "@/features/learning/blocks/types";
import type { ReviewDueItem } from "@/features/learning/blocks/ReviewGateModal";

export type Chapter = {
  id: string;
  title: string;
  origin?: "book" | "prereq"; // prereq = 선행학습 장(적응형 삽입)
  prereqForTitle?: string; // 이 선행이 준비시키는 본편 장 제목(prereq일 때)
  reason?: string | null; // 이유 라벨(서버) — 이 장이 왜 생겼는지(변화 가시성)
  sections: SectionPayload[];
};
export type Course = { id: string; title: string; category: string; chapters: Chapter[] };

export const course: Course = {
  id: "crs_c",
  title: "C언어 프로그래밍 기초",
  category: "프로그래밍 입문",
  chapters: [
    {
      id: "ch1",
      title: "1. C언어 개요 및 환경설정",
      sections: [
        {
          id: "sec1",
          title: "C언어의 역사와 특징",
          blocks: [
            {
              id: "blk_101",
              type: "concept",
              conceptId: "c-history",
              source: "book",
              sourceChunkIds: ["chk_11"],
              verified: true,
              tracked: false,
              data: {
                title: "개념 요약",
                body: "C언어는 1972년 데니스 리치가 유닉스 운영체제를 만들기 위해 개발한 언어입니다. **하드웨어에 가까운 저수준 제어**와 **이식성**을 동시에 잡아, 지금도 운영체제·임베디드의 표준으로 쓰입니다.",
              },
            },
            {
              id: "blk_102",
              type: "mcq",
              conceptId: "c-history",
              kind: "learn",
              source: "ai_prereq",
              externalRefs: [{ title: "C (programming language) — 표준 코퍼스", kind: "corpus" }],
              verified: true,
              tracked: true,
              data: {
                title: "객관식 퀴즈",
                question: "C언어가 처음 만들어진 목적으로 가장 알맞은 것은?",
                options: [
                  "웹 브라우저를 만들기 위해",
                  "유닉스 운영체제를 만들기 위해",
                  "인공지능 연구를 위해",
                ],
                answerIndex: 1,
                explanation: "C는 유닉스를 다시 쓰기 위해 태어난 언어예요. 그래서 OS 개발에 최적화되어 있습니다.",
              },
            },
          ],
        },
        {
          id: "sec2",
          title: "컴파일러 설치 및 첫 코드",
          blocks: [
            {
              id: "blk_201",
              type: "concept",
              conceptId: "compiler",
              source: "book",
              sourceChunkIds: ["chk_18"],
              verified: true,
              tracked: false,
              data: {
                title: "개념 요약",
                body: "사람이 읽는 C 코드를 기계어로 번역하는 도구가 **컴파일러(Compiler)**입니다. `gcc main.c` 처럼 실행하면 실행 파일이 만들어집니다.",
              },
            },
            {
              id: "blk_202",
              type: "cloze",
              conceptId: "compiler",
              kind: "learn",
              source: "ai_prereq",
              externalRefs: [{ title: "Compiler — 표준 코퍼스", kind: "corpus" }],
              verified: true,
              tracked: true,
              data: {
                title: "인출 확인 (빈칸 채우기)",
                segments: [
                  { kind: "text", text: "C 소스 코드를 기계어로 번역하는 프로그램을 " },
                  { kind: "blank", answer: "컴파일러", aliases: ["compiler"] },
                  { kind: "text", text: " 라고 부릅니다." },
                ],
              },
            },
          ],
        },
      ],
    },
    {
      id: "ch2",
      title: "2. 변수와 연산자",
      sections: [
        {
          id: "sec3",
          title: "데이터 타입 (int, float, char)",
          blocks: [
            {
              id: "blk_301",
              type: "concept",
              conceptId: "data-types",
              source: "book",
              sourceChunkIds: ["chk_23"],
              verified: true,
              tracked: false,
              data: {
                title: "개념 요약",
                body: "C의 기본 자료형은 정수 **int**, 실수 **float/double**, 문자 **char**입니다. 자료형에 따라 메모리 크기와 표현 범위가 달라집니다.",
              },
            },
            {
              id: "blk_302",
              type: "mcq",
              conceptId: "data-types",
              kind: "learn",
              source: "ai_prereq",
              externalRefs: [{ title: "C data types — 표준 코퍼스", kind: "corpus" }],
              verified: true,
              tracked: true,
              data: {
                title: "객관식 퀴즈",
                question: "소수점이 있는 숫자(3.14)를 저장하기에 알맞은 자료형은?",
                options: ["int", "char", "float"],
                answerIndex: 2,
                explanation: "int는 정수, char는 문자 하나를 저장해요. 실수는 float(또는 double)에 담습니다.",
              },
            },
          ],
        },
        {
          id: "sec4",
          title: "변수의 선언과 초기화",
          blocks: [
            {
              id: "blk_401",
              type: "concept",
              conceptId: "var-decl",
              source: "book",
              sourceChunkIds: ["chk_31", "chk_32"],
              verified: true,
              tracked: false,
              data: {
                title: "개념 요약",
                body: "메모리에 데이터를 저장하기 위해 공간을 할당받는 것을 **'선언(Declaration)'**이라 하고, 처음으로 값을 집어넣는 것을 **'초기화(Initialization)'**라고 합니다. 선언만 하고 초기화하지 않으면 메모리 안의 알 수 없는 쓰레기 값(Garbage value)이 남게 됩니다.",
              },
            },
            {
              id: "blk_402",
              type: "cloze",
              conceptId: "var-decl",
              kind: "learn",
              source: "ai_prereq",
              externalRefs: [{ title: "Variable declaration — 표준 코퍼스", kind: "corpus" }],
              verified: true,
              tracked: true,
              data: {
                title: "인출 확인 (빈칸 채우기)",
                segments: [
                  {
                    kind: "text",
                    text: "C언어에서 변수를 만들고 처음 값을 넣을 때, `int age;` 과정은 메모리 공간을 만드는 ",
                  },
                  { kind: "blank", answer: "선언" },
                  { kind: "text", text: " 과정이고, `age = 20;` 과정은 처음 값을 넣는 " },
                  { kind: "blank", answer: "초기화" },
                  { kind: "text", text: " 과정입니다." },
                ],
              },
            },
            {
              id: "blk_403",
              type: "mcq",
              conceptId: "var-decl",
              kind: "learn",
              source: "ai_prereq",
              externalRefs: [{ title: "Uninitialized variable — 표준 코퍼스", kind: "corpus" }],
              verified: true,
              tracked: true,
              data: {
                title: "객관식 퀴즈",
                question: "다음 중 초기화되지 않은 변수를 사용할 때 발생하는 문제로 가장 적절한 것은?",
                options: [
                  "컴파일 에러가 발생하며 프로그램이 즉시 종료된다.",
                  "이전 프로그램이 쓰던 의미 없는 쓰레기 값(Garbage value)이 사용된다.",
                  "자동으로 0으로 세팅된다.",
                ],
                answerIndex: 1,
                explanation:
                  "C언어는 지역 변수를 자동으로 초기화하지 않아요. 선언만 하면 그 메모리에 남아 있던 이전 값(가비지)이 그대로 읽힙니다.",
              },
            },
            {
              id: "blk_404",
              type: "explainBack",
              conceptId: "var-decl",
              kind: "learn",
              source: "ai_prereq",
              externalRefs: [{ title: "Variable initialization — 표준 코퍼스", kind: "corpus" }],
              verified: true,
              tracked: true,
              data: {
                title: "파인만식 역질문",
                prompt: "초등학교 5학년 동생에게 '변수 선언'과 '초기화'를 비유를 들어 설명해 보세요.",
                rubric: ["공간 확보(선언)와 값 넣기(초기화)의 구분", "비유 사용"],
              },
            },
          ],
        },
        {
          id: "sec5",
          title: "연산자와 우선순위",
          blocks: [
            {
              id: "blk_501",
              type: "concept",
              conceptId: "operators",
              source: "book",
              sourceChunkIds: ["chk_40"],
              verified: true,
              tracked: false,
              data: {
                title: "개념 요약",
                body: "산술 연산자(+, -, *, /, %)에는 **우선순위**가 있습니다. 수학처럼 곱셈·나눗셈이 덧셈·뺄셈보다 먼저 계산되고, 괄호로 순서를 바꿀 수 있습니다.",
              },
            },
            {
              id: "blk_502",
              type: "cloze",
              conceptId: "operators",
              kind: "learn",
              source: "ai_prereq",
              externalRefs: [{ title: "Modulo operation — 표준 코퍼스", kind: "corpus" }],
              verified: true,
              tracked: true,
              data: {
                title: "인출 확인 (빈칸 채우기)",
                segments: [
                  { kind: "text", text: "`7 % 3` 처럼 나머지를 구하는 연산자의 결과는 " },
                  { kind: "blank", answer: "1" },
                  { kind: "text", text: " 입니다." },
                ],
              },
            },
            {
              id: "blk_503",
              type: "mcq",
              conceptId: "operators",
              kind: "learn",
              source: "ai_prereq",
              externalRefs: [{ title: "Operator precedence — 표준 코퍼스", kind: "corpus" }],
              verified: true,
              tracked: true,
              data: {
                title: "객관식 퀴즈",
                question: "`2 + 3 * 4` 의 결과는?",
                options: ["20", "14", "24"],
                answerIndex: 1,
                explanation: "곱셈이 먼저! 3 * 4 = 12, 그 다음 2 + 12 = 14 입니다.",
              },
            },
          ],
        },
      ],
    },
  ],
};

// 서버(section_progress)가 내려주는 완료 상태 — 초기값. 이후 진행은 화면에서 갱신
export const initialCompletedSectionIds = ["sec1", "sec2", "sec3"];

// 복습 도래 개념 (GET /review/due 응답 모양)
export const reviewDue: ReviewDueItem[] = [
  { concept: "변수의 선언", learnedAgo: "어제" },
  { concept: "Garbage Value", learnedAgo: "어제" },
  { concept: "데이터 타입 int", learnedAgo: "3일 전" },
];
