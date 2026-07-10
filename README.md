# MetaLearn

하이브리드(클라우드 + 로컬) AI 학습 플랫폼. 온라인일 땐 백엔드가 **Upstage Solar**로 학습 콘텐츠를 생성하고, 오프라인일 땐 로컬 **EXAONE**으로 동작하는 것을 목표로 한다.

> **처음 온 사람**: 서비스 정의 → [`docs/SERVICE_OVERVIEW.md`](docs/SERVICE_OVERVIEW.md) · 개발 시작(브랜치 규율·실행법) → [`docs/DEV_GUIDE.md`](docs/DEV_GUIDE.md) · 통합 브랜치 = `feat/yoonhs-integration`

**기본 개념 :** "클라이언트는 컴포넌트를 조립만, 모든 데이터는 JSON 봉투로 온다."
**핵심 :** 개념 그래프 + 숙련도.
→ 개념 그래프 : 책을 개념 점들 + 선행관계 선들로 만든 지도.
→ 숙련도 : 그 지도 위에서 사람마다·개념마다 따로 매기는 이해도 점수.
**불변식:** 사실은 **신뢰 근거**에 묶고, 적응은 학습자 레이어로 위에 얹는다. 책 내용은 책 청크에, 책에 없는 선행은 외부 신뢰 출처에 묶고 AI로 표시한다. **근거 없이 지어낸 사실은 내보내지 않는다.**

---

## 제품 불변 원칙

1. **사실은 근거에, 개인화는 위에.** 책 내용은 업로드된 책 청크에 묶는다. 책에 없는 **선행 개념**은 신뢰 출처(외부 코퍼스·검증된 선행 DB)에 묶고 AI로 표시한다. 어느 쪽이든 *AI가 근거 없이 지어내지 않는다*. 약점·난이도·복습 같은 개인화는 그 위에 얹는 레이어일 뿐, 사실을 새로 만들지 않는다.
2. **검증 안 된 건 안 나간다 — 출처별 기준으로.**
    - `book` → 책 청크에 검증(`source_chunk_ids`).
    - `ai_prereq`(책에 없는 선행) → 신뢰 외부 출처에 검증(`external_ref_ids`) + AI 표시.
    - `analogy`(비유·발판) → 검증 면제(라벨 강제, "사실 아님").
    세 갈래 중 **어디에도 근거를 못 댄 순수 창작 사실**만 노출 금지(`verified=false`).
3. **떠먹이지 않는다.** 정답 요약 대신 빈칸·역질문으로 직접 꺼내게 한다. 막히면 정답이 아니라 *다시 꺼내게 만드는 개입*을 한다.
4. **추적 안 되면 만들지 마라.** 학습 신호(정답/설명/막힘)를 위로 못 올리는 기능은 우리 정체성과 무관하다. ②③ 블록은 반드시 공통 콜백으로 결과를 방출한다.
5. **핵심 단위는 개념(절).** 진단·커리큘럼·생성·추적·복습·연결은 전부 개념 단위에 묶인다. 새 기능은 "이게 어느 개념에 붙나?"로 먼저 따진다.

## 아키텍처 불변 원칙 (어떻게 짤지 막힐 때의 기준)

1. **모든 데이터는 JSON 봉투.** 모든 콘텐츠는 `{id,type,conceptId,source,verified,data}` 봉투로 흐른다. 새 컴포넌트 = 렌더러만 추가, 마이그레이션 0. **HTML을 생성하지 않는다.**
2. **클라이언트는 조립만.** 생성·검증·채점·점수계산은 전부 서버(진실). 프론트는 `registry[type]`로 컴포넌트를 꽂을 뿐, 클라에서 검증/판단하지 않는다.
3. **상태 소유를 섞지 마라.** 진행도·숙련도 = 서버(React Query 미러). 휘발성 UI(현재 절·입력값·포커스) = Zustand. **Zustand에 진행도 저장 금지.**
4. **확장은 type 추가로.** 새 문제 유형·시각화가 필요하면 봉투에 `type`만 늘린다. 구조(래퍼·콜백·레지스트리)는 건드리지 않는다.

## 0. 학습 설계 원칙 (7줄)

1. AI가 떠먹이지 않고 학습자가 직접 꺼내고 설명(인출 중심 메타인지).
2. 핵심 단위 = 개념(절). 진단·커리큘럼·생성·추적·복습·연결이 전부 여기 묶임.
3. 천장(목표 깊이) − 바닥(현재) = 채울 선행. 진단으로 바닥 찾음.
4. 콘텐츠는 책(RAG), 책에 없는 선행은 외부 신뢰 출처 기반 AI 생성. 적응은 누적 상태로.
5. 챕터 진입 시 JIT 생성 = [책 챕터 + 누적 숙련도]. 생성 후 근거(책/외부)에 검증된 블록만 서빙.
6. 답해야 진행(상태머신), 막히면 선제 개입. 서술형은 rubric 채점.
7. 까먹을 때 자동 복습(망각곡선), 연결·설명으로 숲을 키움.

---

## 1. 기술 스택

| 구분 | 기술 | 역할 |
| --- | --- | --- |
| Frontend | React 19, Vite 6, TypeScript, pnpm | SPA, 빠른 HMR |
| 상태관리 | TanStack Query 5, Zustand 5 | (Query) 서버 데이터 캐시 / (Zustand) UI 상태 |
| 라우팅 | react-router-dom 7 | URL ↔ 페이지 매핑 |
| 로컬 저장 | Dexie (IndexedDB) | 오프라인 영속 — Phase 2 |
| 스타일링 | Tailwind CSS 4 | 유틸리티 기반 스타일 (CSS-in-JSX, 토큰은 `@theme`) |
| 아이콘 | Phosphor Icons (`@phosphor-icons/react`) | 아이콘 시스템 (`*Icon` 컴포넌트) |
| 스타일 유틸 | clsx | 조건부 className 조합 (블록 상태별 스타일 분기) |
| Backend | Python 3.12, FastAPI, uv | 비즈니스 로직, Pydantic 검증, AI 연동 |
| ORM/검증 | SQLAlchemy 2.0, Pydantic 2 | DB 매핑 / DTO |
| DB | PostgreSQL 16 + pgvector | 관계형 + 벡터(RAG) 저장 |
| 마이그레이션 | Alembic | 스키마 버전 관리 |
| AI (Cloud) | Upstage Solar | 메인 생성 + 검증/채점 엔진 (OpenAI 호환 API) |
| 외부 근거 | 웹서치 / 표준 교재 코퍼스 / 자체 선행 DB | 책에 없는 선행 개념의 검증 근거 |
| AI (Local) | EXAONE 4.0 1.2B (llama.cpp, Q4) + K-EXAONE(온라인 생성) | 오프라인 채점·꼬리질문 — **데모 MVP 동작** (`feat/ondevice-exaone-mvp`의 `ondevice/`) |

> **임베딩 차원 주의:** `doc_chunks.embedding`은 Solar 임베딩 출력 차원에 맞춘다. 문서 내 `vector(1536)`은 예시값 — 실제 Solar 임베딩 차원으로 확정 후 마이그레이션(불일치 시 색인 실패).
> 

---

## 2. 전체 흐름 — 학습 · 개발 · 데이터 · 요소

| # | 단계 | 학습 | 개발 | 데이터 | 들어갈 요소 |
| --- | --- | --- | --- | --- | --- |
| 1 | 업로드 | 숲 전체 파악 | 파싱 + RAG 색인 + 난이도 추정 | documents, doc_chunks | 업로드 UI, 파서, 임베딩 |
| 2 | 씨앗 | 개념 숲 골격 + 천장 | LLM 개념·선행 그래프 추출(책+AI) | courses, concepts, concept_edges, chapters/sections | 추출 프롬프트, 그래프 빌더 |
| 3 | 진단 | 바닥 찾기 | 진단 블록(봉투) + 그래프 walk-down | blocks(kind=diagnostic), attempts(diagnostic), enrollments | diagnosticStep, walk 알고리즘 |
| 4 | 커리큘럼 | 길 + 전체지도 | 위상정렬 → 챕터/절 순서 | chapters.order_index | conceptMap, 커리큘럼 뷰 |
| 5 | JIT 생성 | 책+내 상태 맞춤 | 챕터 트리거 → RAG+숙련도 → 블록 생성 → 근거 검증(책/외부) → verified만 저장 | chapters.gen_status, blocks(source_chunk_ids, external_ref_ids, verified) | 생성 프롬프트, 검증기 |
| 6 | 스킵 | 알면 압축/모르면 풀 | 확신도 3단계 → variant 분기 | concept_mastery.confidence, section_progress.variant_served | confidenceCheck |
| 7 | 인출 | 직접 꺼내·설명 | registry 조립, onAnswer. 객관식=correct / explainBack=LLM rubric 채점→score | blocks↓ attempts↑ | cloze/mcq/explainBack, MathText, 선제개입 |
| 8 | 추적 | 개념별 숙련도(절→장%) | 점수계산(서버), RQ 동기화, 잠금. explanation_score는 서술 채점 결과로 갱신 | concept_mastery, section_progress | 진행률 위젯, 잠금 게이트 |
| 9 | 복습 | 까먹을 때 자동 | next_due 스케줄, 통과↑/틀림 리셋 + 알림 | concept_mastery, attempts(review), notifications | reviewGate, 스케줄러 |
| 10 | 숲 | 옛+새 연결 | concept_edges로 연결퀴즈·지도 | concept_edges, attempts(connection) | connection, conceptMap, explainBack |
| + | 결제 | Pro로 무제한 | 구독·결제·웹훅 | plans, subscriptions, payments | 결제 UI, 프로바이더 웹훅 |
| + | 알림 | 적시 소환 | 복습/생성완료/스트릭 푸시 | notifications, push_tokens | 인앱/푸시 |

---

## 2.5 검증·채점 파이프라인

### A. 생성 검증 (출처별 faithfulness) — 5단계 내부

블록의 `source`에 따라 **무엇에 대조하는지**가 달라진다. 공통 목표는 "근거 없이 지어낸 사실을 막는 것".

```
[1] 근거 확보:
      source=book      → RAG로 책 청크 확보 (doc_chunks)
      source=ai_prereq → 외부 신뢰 출처 확보 (웹서치/표준 코퍼스/선행 DB)
[2] 생성: 블록 data 생성  입력 = [근거 + 누적 숙련도]
[3] 검증: 생성된 각 "사실 문장"이 근거에 의해 뒷받침되는가? (Solar 판정 — 별도 콜)
            ├─ book      통과 → verified=true, source_chunk_ids 기록
            ├─ ai_prereq 통과 → verified=true, external_ref_ids 기록(+🤖 표시)
            └─ 실패 → 재생성 1회 → 또 실패면 블록 폐기(범위 갭 표시, 서빙 안 함)
[4] 서빙: verified=true 인 블록만 클라이언트로
```

- **규칙:** 어떤 블록도 근거(`source_chunk_ids` 또는 `external_ref_ids`) 없이 `verified=true`가 될 수 없다.
- **선행(`ai_prereq`)은 반드시 AI + 출처 표기:** 학생이 "이건 교재 밖 보충 설명"임을 항상 알게 한다(`external_refs`를 인용 배지로 렌더).
- **비유(`analogy`)는 예외:** "사실 아님" 라벨이 붙은 발판이므로 검증 면제(대신 라벨 강제).
- **위험도 차등:** 정의·공식 같은 고위험 선행은 외부 검증을 강하게(복수 출처 일치), 맥락 설명은 약하게.
- **오프라인(EXAONE):** 로컬은 서버 검증·외부 검색을 못 받음 → 정책은 §12 참조(오프라인은 *생성 금지, 검증된 캐시 재생만*).

### B. 채점 (정답 유형별) — 7단계 내부

| 블록 유형 | 채점 방식 | 기록 |
| --- | --- | --- |
| 객관식·빈칸·OX (`mcq`/`cloze`/`trueFalse`) | 정오 비교 | `attempts.correct` (boolean) |
| 서술형 (`explainBack`) | Solar가 학생 설명 vs `rubric[]` 키포인트 채점 → 0~1 점수 + 놓친 포인트 | `attempts.score` + `concept_mastery.explanation_score` |
| 탐색형 (`sliderExplore` 등) | 정답 없음 — 상호작용 신호만 | `attempts.correct=null`, `kind`로 구분 |

```
explainBack 제출
  → POST /attempts (kind=learn, type=explainBack)
  → 서버: Solar 채점(설명 vs rubric) → {score, feedback, missedPoints[]}
  → attempts.score 기록
  → concept_mastery.explanation_score 갱신 → strength 재계산
  → 응답에 {score, feedback, missedPoints} 포함 (프론트가 피드백 렌더)
```

### C. 선제 개입 (막히면 묻기 전에) — 7단계 내부

학습자가 막히는 신호를 감지하면, 사용자가 도움을 요청하기 전에 AI가 먼저 개입한다.

**막힘 감지 트리거 (`attempts`/세션에서 읽음)**

- 같은 개념 연속 오답 2회 이상
- 한 블록에서 입력 없이 머문 시간 초과(프론트 타이머 → 신호)
- 사용자가 명시적으로 힌트 요청

**개입 단계 (점진적, `hintLadder` 블록 활용)**

```
막힘 감지
  → 1차: 다른 각도의 질문 / 비유(analogy, "사실 아님" 라벨)
  → 2차: 단계별 힌트(hintLadder — 점진 공개)
  → 3차: 선행 개념으로 잠깐 되돌림(concept_edges prerequisite)
  → 회복되면 원래 흐름 복귀
```

- 개입은 *정답을 주는 게 아니라* 다시 꺼내게 만드는 방향(인출 보존).
- 개입 발생은 `attempts.meta`에 기록 → 약점 추적에 반영.

### D. 숲 키우기 (연결) — 콘텐츠 생성 규칙

1. **시작에 전체 지도** — 코스/챕터 진입 시 conceptMap으로 "지금 여기 → 나중에 저기" 표시.
2. **매 개념 "왜 배우나" 앞연결** — 개념 생성 시, 이 개념이 뒤(상위/응용)에서 어디에 쓰이는지 한 줄을 `concept` 블록에 포함(concept_edges application 참조).
3. **챕터 끝 통합 설명** — 챕터 종료 지점에 "이 개념들이 어떻게 같이 작동하는지 설명해봐" `explainBack` 블록 배치(스스로 조립).
4. **간격 복습으로 옛 개념 살려두기** — 복습 스케줄이 옛 개념을 살아있게 유지 → 새 개념과 연결될 때 인출 가능(§9 복습과 연동).

---

## 3. 프론트엔드 컴포넌트 설계 원칙 (UI/UX)

학습 루프를 구성하는 모든 블록은 3가지 범주로 나뉜다.

- **① 설명 (보여준다):** 개념 본문·차트 등 (추적 ❌)
- **② 문제 (꺼내게 한다):** 빈칸·객관식·역질문 등 (추적 ✅, 회피 불가)
- **③ 인터랙티브 (조작하게 한다):** 슬라이더·시뮬레이션 등 (추적 ✅)

**UI 4대 원칙**

1. **컴포넌트 고정 + 데이터 주입** — 컴포넌트는 HTML을 생성하지 않고 JSON 데이터만 채움.
2. **공통 래퍼 통일** — 모든 블록은 `type`으로 컴포넌트를 고르고 동일 래퍼 사용.
3. **답해야 진행** — ②③ 블록은 상태머신 내장, 답 전엔 다음으로 못 감.
4. **추적 콜백 공유** — `onAnswer({blockId, conceptId, correct, score})` 공통 콜백으로 숙련도 추적. (탐색형은 `onInteract`)
5. **출처 배지** — `source`에 따라 (book)/(ai_prereq)/(analogy) 배지를 렌더. ai_prereq는 `external_refs`를 인용으로 노출.

> 컴포넌트 카탈로그(41종)·우선순위는 `MetaLearn-UI-컴포넌트-브리프.md` 참고. 수식 렌더(MathText)는 모든 텍스트 블록의 공통 기능으로 깔며, 코딩/수학 타깃 시 `codeExercise`·`mathInput`을 1차에 포함.
> 

---

## 4. DB 스키마 (PostgreSQL)

> 스키마(ENUM·테이블·컬럼 설명)는 **[docs/SCHEMA.md](docs/SCHEMA.md)** 로 분리했다.

---

## 5. 공통 블록 봉투 (모든 콘텐츠의 단위)

```json
// 책 내용 (📖)
{ "id":"blk_017","type":"cloze","conceptId":"act-fn",
  "source":"book","sourceChunkIds":["chk_3","chk_7"],"externalRefs":[],
  "verified":true,"data":{ },"meta":{"difficulty":"mid","version":1} }

// 책에 없는 선행 (외부 근거 + 🤖)
{ "id":"blk_018","type":"concept","conceptId":"calculus-basic",
  "source":"ai_prereq","sourceChunkIds":[],
  "externalRefs":[{"title":"미분 기본정리","url":"...","kind":"corpus"}],
  "verified":true,"data":{ "badge":"🤖 교재 밖 보충" } }

// 비유 (💡, 검증 면제·라벨 강제)
{ "id":"blk_019","type":"analogy","conceptId":"act-fn",
  "source":"analogy","verified":true,
  "data":{ "label":"비유","text":"활성화 함수는 수도꼭지처럼..." } }
```

- `data`의 41개 모양은 공유 스키마가 단일 소유 → AI 생성 타깃 + 서버 검증(Pydantic) + 클라 타입(TS)이 한 소스에서 생성(스키마 드리프트 방지).
- 진단/지도/확신도/복습/연결도 전부 같은 봉투 `type` → 새 컴포넌트 = 클라 렌더러만 추가, 마이그레이션 0.
- `verified=false` 블록은 서빙 금지. `source`별 근거 규칙은 §2.5A·§4 주석 참조.

---

## 6. API 명세 (🔒 = 인증 필요)

> 전체 API 명세는 **[docs/API.md](docs/API.md)** 로 분리했다.

---

## 7. 데이터 주고받는 형태 (핵심 교환)

**절 로드** `GET /sections/sec_3`

```json
{ "sectionId":"sec_3","conceptId":"act-fn","variant":"full",
  "blocks":[
    {"id":"blk_017","type":"cloze","source":"book","verified":true,
     "sourceChunkIds":["chk_3"],"data":{ }},
    {"id":"blk_018","type":"concept","source":"ai_prereq","verified":true,
     "externalRefs":[{"title":"미분 기본정리","url":"..."}],"data":{"badge":"🤖 교재 밖 보충"}}
  ] }
```

**정답 기록 (객관식)** `POST /attempts`

```json
// → { "blockId":"blk_017","conceptId":"act-fn","kind":"learn","correct":true,"userInput":1 }
// ← { "concept":{"conceptId":"act-fn","strength":0.62,"status":"learning",
//                "nextDueAt":"2026-07-02T09:00:00Z"} }
```

**정답 기록 (explainBack — 서술 채점)** `POST /attempts`

```json
// → { "blockId":"blk_022","conceptId":"act-fn","kind":"learn",
//     "type":"explainBack","userInput":"활성화 함수는 비선형성을 더해서..." }
// ← { "score":0.7,
//     "feedback":{ "missedPoints":["기울기 소실 언급 없음"], "comment":"핵심은 짚었어요" },
//     "concept":{ "conceptId":"act-fn","explanationScore":0.7,"strength":0.66,
//                 "status":"learning","nextDueAt":"2026-07-03T09:00:00Z" } }
```

**진단(적응)** `POST /courses/crs_1/diagnostic/answer`

```json
// → { "conceptId":"c2","correct":false }
// ← { "next":{"conceptId":"c1","block":{봉투}}, "progress":{"asked":4,"max":15} }
//   종료: { "done":true,"floor":"c1","ceiling":"c5" }
```

**복습 due** `GET /review/due?courseId=crs_1`

```json
{ "dueConcepts":["c1","c4"], "gate":{ /* reviewGate 봉투 */ } }
```

---

## 8. 클라 ↔ 서버 경계 (상태 소유)

!image.png

- 검증: 서버 쓰기/생성 시. 클라는 공유 타입 신뢰(런타임 zod X).
- 진행도/숙련도: 서버 source of truth → React Query 미러(낙관적 업데이트).
- Zustand: 진행도 저장 금지, 화면 임시 상태만.

---

## 9. 폴더 구조 및 구현 상태

```
metalearn/
├── docker-compose.yml
├── backend/                    # FastAPI (Python 3.12 + uv)
│   ├── alembic/
│   └── app/
│       ├── main.py             # FastAPI 인스턴스, CORS·미들웨어
│       ├── api.py              # features 라우터를 /api로 통합
│       ├── core/               # 공통 시스템 모듈
│       │   ├── config.py       # .env 파싱
│       │   ├── database.py     # DB 세션
│       │   ├── security.py     # JWT·해싱
│       │   ├── verify_grade.py # ★ 출처별 검증 + 서술 채점
│       │   ├── retrieval.py    # ★ 책 RAG + 외부 근거(웹서치/코퍼스/선행DB)
│       │   └── llm/            # AI 연동 공통 인터페이스
│       │       ├── base.py     # 추상 인터페이스(온/오프라인 공통)
│       │       └── solar.py    # Upstage Solar 구현체
│       └── features/           # 도메인별 격리 (Router→Schema→Service→Repository→Model)
│           ├── auth/           # ⬜ [골격]
│           ├── seed/           # ⬜ [골격] 씨앗(개념 그래프) 공장
│           ├── materials/      # ⬜ [골격] 업로드·파싱·RAG 색인
│           ├── curriculum/     # ⬜ [골격] 위상정렬·챕터/절 순서
│           ├── learning/       # ✅ [완료] 핵심 학습 루프
│           └── review/         # ⬜ [골격] 복습 알고리즘
└── frontend/                   # React 19 + Vite (FSD)
    └── src/
        ├── app/                # 라우터(routes.tsx), QueryClient
        ├── pages/              # URL ↔ 화면 조립(레이아웃만)
        ├── shared/             # 공용 ui·api·utils(네트워크 상태 체크)
        ├── runtime/            # ★ 온라인(API)/오프라인(EXAONE) 분기
        │   ├── provider.ts     # 온·오프라인 판단 → 요청 분기
        │   └── engine.ts       # 로컬 EXAONE Web Worker 엔진
        ├── storage/            # ⬜ [Phase 2] Dexie(IndexedDB)
        └── features/           # 도메인별 (api→queries→components, store.ts, prompts.ts)
            ├── curriculum/     # ✅ [UI 완료]
            ├── learning/       # ✅ [완료]
            ├── dashboard/      # ✅ [UI 완료]
            ├── createCourse/   # ✅ [UI 완료]
            ├── landing/        # ✅ [UI 완료]
            ├── onboarding/     # ✅ [UI 완료]
            ├── seed/           # ⬜ [골격]
            └── review/         # ⬜ [골격]
```

---

## 10. 구현 순서 (MVP 컷)

1. **인프라:** auth + documents 업로드/파싱 + 코스 골격
2. **엔진:** 블록 봉투 + registry + 1차 5블록(concept/cloze/mcq/explainBack/reviewGate) + MathText
3. **핵심 루프:** 절 로드 → 인출 → POST /attempts → progress 잠금 ← 제품의 심장
    - explainBack 채점 경로(2.5B) 포함 — boolean 아님, score로
4. **개념 그래프:** 씨앗 생성(2) + 진단(3) + 커리큘럼(4) + 전체지도
5. **JIT 생성(5) + 출처별 검증(2.5A)** + 확신도 스킵(6)
    - book은 책 RAG, ai_prereq는 외부 근거 검색 → 둘 다 verified만 서빙
    - 챕터 prefetch(다음 챕터 백그라운드 생성)로 로딩 벽 방지
6. **복습(9) + 알림(복습 due 푸시)**
7. **연결/숲(10) + 메타인지 분석 화면**
8. **결제/구독(Pro 게이트)**

> 화면 1개씩 브라우저로 실제 확인해야 '완료'. tsc 통과 = 완료 아님. 콘텐츠/진행 모든 표시는 데이터에서. 하드코딩 금지.
> 

---

## 11. 실행 방법

```bash
docker compose up --build
docker compose exec backend uv run alembic upgrade head
```

| 서비스 | 주소 |
| --- | --- |
| Frontend (Vite dev) | http://localhost:5173 |
| Backend (FastAPI) | http://localhost:8000 |
| API 문서 (Swagger) | http://localhost:8000/docs |
| PostgreSQL | localhost:5432 (postgres / dev / metalearn) |

**환경 변수**

- `backend/.env`: `SECRET_KEY`, `UPSTAGE_API_KEY` 필수(생성·검증·채점). 선행 외부근거용 검색 키(웹서치)도 필요 시 추가.
- `frontend/.env`: `VITE_API_BASE_URL` (기본 http://localhost:8000)

---

## 12. 오프라인(로컬 EXAONE) 정책 — Phase 2

로컬은 서버 검증·외부 근거 검색을 못 받으므로, **오프라인에서는 새 콘텐츠를 생성하지 않는다.** 로컬의 역할은 *생성기*가 아니라 *플레이어*다.

- **온라인일 때** 다음 챕터들을 미리 생성+검증해 **검증된 봉투를 IndexedDB(Dexie)에 캐시**(prefetch).
- **오프라인일 때** EXAONE은 캐시된 검증 블록을 풀게 하고, **저위험 보조(힌트·격려·서술 채점 보조)만** 담당. 사실 생성 금지.
- 오프라인에서 쌓인 attempts·숙련도는 **온라인 복귀 시 동기화 큐**로 서버에 머지.
- 이 원칙으로 "검증 안 된 건 안 나간다"(제품 원칙 2)가 오프라인에서도 유지된다.

### 채워진 것 vs 빈 골격

| 영역 | 상태 |
| --- | --- |
| 인프라 (compose, Dockerfile ×2, .env, .gitignore) | ✅ 동작 |
| backend `core/` (config, database, security, llm) | ✅ 동작 |
| backend `features/learning/` | ✅ 데모(generate) + JIT 적응형 커리큘럼(점수 분기 선수+브릿지 / 메인100%, 인출형 블록) |
| backend `features/materials/` | ✅ Ingestion 파이프라인 (PDF→파싱→개념/선수지식 그래프→pgvector) |
| backend `features/diagnostic/` | ✅ BKT 정밀 진단 (불확실성 타겟팅 + MCQ/빈칸/역질문 혼합 + LLM 심판 채점 + 유형별 추측률 + 신뢰도 수렴) |
| backend `features/{auth,seed,review}/` | ⬜ 빈 `router.py`만 (엔드포인트 0) |
| frontend `app/`·`shared/`·`pages/`·`runtime(online)` | ✅ 동작 |
| frontend `features/learning/` | ✅ 데모 패널 + JIT 커리큘럼 뷰(인출형 블록, `/curriculum`) |
| frontend `features/materials/` | ✅ 업로드 패널 + 개념 그래프 뷰 (`/materials`) |
| frontend `features/diagnostic/` | ✅ 진단 루프 UI + 숙련도 패널 (`/diagnostic`) |
| frontend `features/{seed,review}/` | ⬜ `.gitkeep`만 |
| 로컬 EXAONE (`runtime/engine.ts`), Dexie (`storage/db.ts`) | ⬜ Phase 2 스텁 |

> `__init__.py`는 파이썬 패키지 표식(빈 파일, 삭제 금지). 백엔드 폴더마다 존재.

---

## 부록. 구현 전 확정 항목

- [ ]  41 type 공유 스키마 단일 소스 파이프라인 구축 (백·프론트·LLM 동시 공급)
- [ ]  Solar 임베딩 차원 확정 후 `doc_chunks.embedding` 마이그레이션
- [ ]  외부 근거 소스 확정(웹서치 제공자 / 표준 코퍼스 / 자체 선행 DB 중 무엇으로 시작할지)