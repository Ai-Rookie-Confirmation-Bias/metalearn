# MetaLearn

하이브리드(클라우드 + 로컬) AI 학습 플랫폼. 온라인일 땐 백엔드가 **Upstage Solar**로 학습 콘텐츠를 생성하고, 오프라인일 땐 브라우저 내 로컬 **EXAONE**으로 동작하는 것을 목표로 한다.

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
| AI (Local) | EXAONE (wllama/WebGPU) | 오프라인/무료 — Phase 2, 스텁 |

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

- 스키마
    
    ```sql
    -- ── ENUMS ──────────────────────────────────────────────
    CREATE TYPE document_status AS ENUM ('processing','ready','failed');
    CREATE TYPE gen_status      AS ENUM ('pending','generating','ready','failed');
    CREATE TYPE chapter_origin  AS ENUM ('book','prereq');
    CREATE TYPE content_source  AS ENUM ('book','ai_prereq','analogy');  -- 📖 책 / 🤖 선행(외부근거) / 💡 비유
    CREATE TYPE edge_kind       AS ENUM ('prerequisite','related','application');
    CREATE TYPE mastery_status  AS ENUM ('locked','todo','learning','mastered');
    CREATE TYPE confidence_lvl  AS ENUM ('sure','ambiguous','unknown');
    CREATE TYPE serve_variant   AS ENUM ('full','compressed','quick');
    CREATE TYPE attempt_kind    AS ENUM ('diagnostic','learn','review','connection');
    CREATE TYPE progress_status AS ENUM ('not_started','in_progress','completed');
    CREATE TYPE diag_status     AS ENUM ('not_started','in_progress','completed');
    CREATE TYPE plan_tier       AS ENUM ('free','pro');
    CREATE TYPE sub_status      AS ENUM ('trialing','active','past_due','canceled');
    CREATE TYPE payment_status  AS ENUM ('paid','failed','refunded');
    CREATE TYPE notif_type      AS ENUM ('review_due','generation_ready','streak','system');
    
    -- ╔ A. 콘텐츠 + 개념 그래프 ╗
    CREATE TABLE users (                         -- 소셜 로그인(구글/네이버) 기준
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      email text UNIQUE NOT NULL,                -- 소셜에서 받음
      provider text NOT NULL,                    -- 'google' | 'naver'
      provider_uid text NOT NULL,                -- 소셜 고유 ID(sub) — 계정 연결 키
      nickname text,                             -- 표시명(프로필 설정에서 입력)
      name text,                                 -- 소셜 실명(선택)
      avatar_url text,                           -- 소셜 프로필 이미지(선택)
      created_at timestamptz NOT NULL DEFAULT now(),
      UNIQUE (provider, provider_uid)
    );
    
    CREATE TABLE documents (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      user_id uuid NOT NULL REFERENCES users(id),
      filename text NOT NULL,
      storage_url text NOT NULL,
      raw_text text,
      difficulty_est smallint,                 -- 천장 추정 입력(1~10)
      status document_status NOT NULL DEFAULT 'processing',
      created_at timestamptz NOT NULL DEFAULT now()
    );
    
    CREATE TABLE doc_chunks (                   -- RAG 청크(📖 인용 근거 + 검증 대상)
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      document_id uuid NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
      chunk_index int NOT NULL,
      content text NOT NULL,
      embedding vector(1536),                  -- ※ Solar 임베딩 차원에 맞춰 확정
      page_from int, page_to int
    );
    CREATE INDEX ON doc_chunks USING ivfflat (embedding vector_cosine_ops);
    
    CREATE TABLE courses (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      document_id uuid NOT NULL REFERENCES documents(id),
      user_id uuid NOT NULL REFERENCES users(id),
      title text NOT NULL, category text,
      created_at timestamptz NOT NULL DEFAULT now()
    );
    
    CREATE TABLE concepts (                     -- ★ 개념 노드(절의 핵심 = 숲의 점)
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      course_id uuid NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
      key text NOT NULL,
      name text NOT NULL, description text,
      source content_source NOT NULL,           -- 📖 book / 🤖 ai_prereq
      depth_level smallint,                     -- 천장/바닥 좌표
      UNIQUE (course_id, key)
    );
    
    -- ★ 책에 없는 선행 개념의 외부 신뢰 근거 (웹서치/표준 코퍼스/선행 DB)
    CREATE TABLE external_refs (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      concept_id uuid REFERENCES concepts(id) ON DELETE CASCADE,
      source_kind text NOT NULL,               -- 'web' | 'corpus' | 'prereq_db'
      title text,
      url text,
      snippet text,                            -- 검증에 사용된 근거 발췌
      created_at timestamptz NOT NULL DEFAULT now()
    );
    CREATE INDEX ON external_refs (concept_id);
    
    CREATE TABLE concept_edges (
      from_concept_id uuid NOT NULL REFERENCES concepts(id) ON DELETE CASCADE,
      to_concept_id   uuid NOT NULL REFERENCES concepts(id) ON DELETE CASCADE,
      kind edge_kind NOT NULL,
      PRIMARY KEY (from_concept_id, to_concept_id, kind)
    );
    CREATE INDEX ON concept_edges (to_concept_id);
    
    CREATE TABLE chapters (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      course_id uuid NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
      order_index int NOT NULL, title text NOT NULL,
      origin chapter_origin NOT NULL DEFAULT 'book',
      gen_status gen_status NOT NULL DEFAULT 'pending'  -- ★ JIT 트리거(챕터 단위)
    );
    
    CREATE TABLE sections (                     -- 절(학습·추적 단위, 개념과 1:1)
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      chapter_id uuid NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
      concept_id uuid REFERENCES concepts(id),
      order_index int NOT NULL, title text NOT NULL
    );
    
    CREATE TABLE blocks (                       -- ★ 컴포넌트 = JSON 봉투
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      section_id uuid REFERENCES sections(id) ON DELETE CASCADE, -- nullable: 진단 블록은 절에 안 묶임
      order_index int NOT NULL DEFAULT 0,
      type text NOT NULL,                       -- 'concept','mcq','cloze','explainBack','diagnostic'...
      kind attempt_kind,                        -- 진단/학습/복습/연결 구분
      concept_id uuid REFERENCES concepts(id),
      source content_source NOT NULL,           -- book / ai_prereq / analogy
      tracked boolean NOT NULL DEFAULT false,   -- ②③ 정답 추적 대상
      -- ★ 근거(출처별) + 검증
      source_chunk_ids uuid[] NOT NULL DEFAULT '{}',  -- book 근거: 책 청크
      external_ref_ids uuid[] NOT NULL DEFAULT '{}',  -- ai_prereq 근거: 외부 신뢰 출처
      verified boolean NOT NULL DEFAULT false,        -- 근거 대조 통과(true만 서빙)
      data jsonb NOT NULL,                       -- type별 알맹이(불투명, 서버 검증)
      meta jsonb NOT NULL DEFAULT '{}'::jsonb
    );
    CREATE INDEX ON blocks (section_id, order_index);
    CREATE INDEX ON blocks (concept_id, kind);
    -- 검증 규칙(앱 레벨): verified=true 이려면
    --   source='book'      → source_chunk_ids 비어있지 않음
    --   source='ai_prereq' → external_ref_ids 비어있지 않음
    --   source='analogy'   → data.label='비유' 필수(검증 면제)
    
    -- ╔ B. 학습자 계층 (user×concept / 가변) ╗
    CREATE TABLE enrollments (
      user_id uuid NOT NULL REFERENCES users(id),
      course_id uuid NOT NULL REFERENCES courses(id),
      ceiling_concept uuid REFERENCES concepts(id),  -- 천장(목표)
      floor_concept uuid REFERENCES concepts(id),    -- 진단 결과 바닥
      floor_found boolean NOT NULL DEFAULT false,
      diag_status diag_status NOT NULL DEFAULT 'not_started',
      diag_q_count int NOT NULL DEFAULT 0,
      self_report jsonb,                              -- {grade, major}
      created_at timestamptz NOT NULL DEFAULT now(),
      PRIMARY KEY (user_id, course_id)
    );
    -- 진단 문항 = blocks(kind='diagnostic'), 진단 응답 = attempts(kind='diagnostic'),
    -- 진단 진행 = enrollments.diag_* 로 관리(별도 진단 테이블 없음).
    
    CREATE TABLE concept_mastery (              -- ★ 숙련도 + 복습 스케줄
      user_id uuid NOT NULL REFERENCES users(id),
      concept_id uuid NOT NULL REFERENCES concepts(id),
      status mastery_status NOT NULL DEFAULT 'locked',
      strength real NOT NULL DEFAULT 0,         -- 종합 0~1 (정답률·인출 가중 합산)
      explanation_score real NOT NULL DEFAULT 0,-- ★ explainBack 서술 채점 결과
      confidence confidence_lvl,
      ease real NOT NULL DEFAULT 2.5,           -- SM-2
      interval_days int NOT NULL DEFAULT 0,
      last_reviewed_at timestamptz,
      next_due_at timestamptz,                  -- ★ 망각곡선
      PRIMARY KEY (user_id, concept_id)
    );
    CREATE INDEX ON concept_mastery (user_id, next_due_at);
    
    CREATE TABLE attempts (                     -- 모든 시도(append-only) — 진단 포함
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      user_id uuid NOT NULL REFERENCES users(id),
      block_id uuid REFERENCES blocks(id),
      concept_id uuid NOT NULL REFERENCES concepts(id),
      kind attempt_kind NOT NULL,               -- diagnostic/learn/review/connection
      correct boolean,                          -- nullable: 서술형/탐색형은 null
      score real,                               -- 0~1 부분점수(explainBack 등)
      user_input jsonb,
      feedback jsonb,                           -- {missedPoints[], comment} 서술 채점 피드백
      meta jsonb NOT NULL DEFAULT '{}'::jsonb,  -- 막힘 신호·개입 이력 등
      created_at timestamptz NOT NULL DEFAULT now()
    );
    CREATE INDEX ON attempts (user_id, concept_id, created_at);
    
    CREATE TABLE section_progress (
      user_id uuid NOT NULL REFERENCES users(id),
      section_id uuid NOT NULL REFERENCES sections(id),
      status progress_status NOT NULL DEFAULT 'not_started',
      variant_served serve_variant,
      completed_at timestamptz,
      PRIMARY KEY (user_id, section_id)
    );
    
    -- ╔ C. 결제/구독 ╗
    CREATE TABLE plans (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      tier plan_tier NOT NULL,
      name text NOT NULL,
      price_cents int NOT NULL,
      interval text NOT NULL DEFAULT 'month'
    );
    CREATE TABLE subscriptions (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      user_id uuid NOT NULL REFERENCES users(id),
      plan_id uuid NOT NULL REFERENCES plans(id),
      status sub_status NOT NULL,
      current_period_end timestamptz,
      provider text,
      provider_sub_id text,
      created_at timestamptz NOT NULL DEFAULT now()
    );
    CREATE TABLE payments (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      user_id uuid NOT NULL REFERENCES users(id),
      subscription_id uuid REFERENCES subscriptions(id),
      amount_cents int NOT NULL,
      status payment_status NOT NULL,
      provider_payment_id text,
      created_at timestamptz NOT NULL DEFAULT now()
    );
    
    -- ╔ D. 알림 ╗
    CREATE TABLE notifications (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      user_id uuid NOT NULL REFERENCES users(id),
      type notif_type NOT NULL,
      title text NOT NULL, body text,
      data jsonb,                               -- {courseId, conceptId, ...} 딥링크
      read_at timestamptz,
      created_at timestamptz NOT NULL DEFAULT now()
    );
    CREATE INDEX ON notifications (user_id, read_at);
    CREATE TABLE push_tokens (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      user_id uuid NOT NULL REFERENCES users(id),
      token text NOT NULL,
      platform text NOT NULL,
      created_at timestamptz NOT NULL DEFAULT now(),
      UNIQUE (token)
    );
    ```
    
- 한글
    
    ## 📌 ENUM (열거형 타입) 정의
    
    | **타입명** | **허용 값 (Values)** |
    | --- | --- |
    | **문서 처리 상태 (`document_status`)** | `processing`, `ready`, `failed` |
    | **생성 상태 (`gen_status`)** | `pending`, `generating`, `ready`, `failed` |
    | **챕터 출처 (`chapter_origin`)** | `book`, `prereq` |
    | **콘텐츠 출처 (`content_source`)** | `book`, `ai_prereq`, `analogy` |
    | **개념 연결 종류 (`edge_kind`)** | `prerequisite`, `related`, `application` |
    | **숙련도 상태 (`mastery_status`)** | `locked`, `todo`, `learning`, `mastered` |
    | **확신도 (`confidence_lvl`)** | `sure`, `ambiguous`, `unknown` |
    | **제공 형태 (`serve_variant`)** | `full`, `compressed`, `quick` |
    | **시도/학습 종류 (`attempt_kind`)** | `diagnostic`, `learn`, `review`, `connection` |
    | **진행 상태 (`progress_status`)** | `not_started`, `in_progress`, `completed` |
    | **진단 상태 (`diag_status`)** | `not_started`, `in_progress`, `completed` |
    | **요금제 등급 (`plan_tier`)** | `free`, `pro` |
    | **구독 상태 (`sub_status`)** | `trialing`, `active`, `past_due`, `canceled` |
    | **결제 상태 (`payment_status`)** | `paid`, `failed`, `refunded` |
    | **알림 유형 (`notif_type`)** | `review_due`, `generation_ready`, `streak`, `system` |
    
    ## ╔ A. 콘텐츠 + 개념 그래프 ╗
    
    ### 사용자 (`users`)
    
    | **컬럼명** | **데이터 타입** | **제약조건** |
    | --- | --- | --- |
    | **사용자 고유 식별자 (`id`)** | `uuid` | PK, 기본값 |
    | **이메일 주소 (`email`)** | `text` | UNIQUE, NOT NULL (소셜에서 받음) |
    | **소셜 제공자 (`provider`)** | `text` | NOT NULL (`google`/`naver`) |
    | **소셜 고유 ID (`provider_uid`)** | `text` | NOT NULL — 계정 연결 키(sub) |
    | **표시명 (`nickname`)** | `text` | 프로필 설정에서 입력 |
    | **실명 (`name`)** | `text` | 선택(소셜 제공) |
    | **프로필 이미지 (`avatar_url`)** | `text` | 선택(소셜 제공) |
    | **계정 생성 일시 (`created_at`)** | `timestamptz` | NOT NULL, 기본값(now) |
    | **(소셜 계정 유니크)** | — | UNIQUE(`provider`, `provider_uid`) |
    
    ### 문서 정보 (`documents`)
    
    | **컬럼명** | **데이터 타입** | **제약조건** |
    | --- | --- | --- |
    | **문서 고유 식별자 (`id`)** | `uuid` | PK, 기본값 |
    | **업로드한 사용자 ID (`user_id`)** | `uuid` | FK, NOT NULL |
    | **파일명 (`filename`)** | `text` | NOT NULL |
    | **저장소 URL (`storage_url`)** | `text` | NOT NULL |
    | **추출된 원본 텍스트 (`raw_text`)** | `text` |  |
    | **천장 추정 난이도 입력 (`difficulty_est`)** | `smallint` |  |
    | **문서 처리 상태 (`status`)** | `document_status` | NOT NULL, 기본값('processing') |
    | **생성 일시 (`created_at`)** | `timestamptz` | NOT NULL, 기본값(now) |
    
    ### RAG 문서 청크 (`doc_chunks`)
    
    | **컬럼명** | **데이터 타입** | **제약조건** |
    | --- | --- | --- |
    | **청크 고유 식별자 (`id`)** | `uuid` | PK, 기본값 |
    | **원본 문서 ID (`document_id`)** | `uuid` | FK, NOT NULL, CASCADE |
    | **청크 순서 인덱스 (`chunk_index`)** | `int` | NOT NULL |
    | **분할된 텍스트 내용 (`content`)** | `text` | NOT NULL |
    | **벡터 임베딩 (`embedding`)** | `vector(1536)` |  |
    | **시작 페이지 (`page_from`)** | `int` |  |
    | **끝 페이지 (`page_to`)** | `int` |  |
    
    ### 코스/과정 (`courses`)
    
    | **컬럼명** | **데이터 타입** | **제약조건** |
    | --- | --- | --- |
    | **코스 고유 식별자 (`id`)** | `uuid` | PK, 기본값 |
    | **기반 문서 ID (`document_id`)** | `uuid` | FK, NOT NULL |
    | **코스 소유자 ID (`user_id`)** | `uuid` | FK, NOT NULL |
    | **코스 제목 (`title`)** | `text` | NOT NULL |
    | **카테고리 (`category`)** | `text` |  |
    | **생성 일시 (`created_at`)** | `timestamptz` | NOT NULL, 기본값(now) |
    
    ### 개념 노드 (`concepts`)
    
    | **컬럼명** | **데이터 타입** | **제약조건** |
    | --- | --- | --- |
    | **개념 고유 식별자 (`id`)** | `uuid` | PK, 기본값 |
    | **소속 코스 ID (`course_id`)** | `uuid` | FK, NOT NULL, CASCADE |
    | **개념 키 (`key`)** | `text` | NOT NULL |
    | **개념 이름 (`name`)** | `text` | NOT NULL |
    | **개념 설명 (`description`)** | `text` |  |
    | **출처 (`source`)** | `content_source` | NOT NULL |
    | **천장/바닥 좌표 (`depth_level`)** | `smallint` |  |
    
    ### 외부 신뢰 근거 (`external_refs`)
    
    | **컬럼명** | **데이터 타입** | **제약조건** |
    | --- | --- | --- |
    | **외부 근거 고유 식별자 (`id`)** | `uuid` | PK, 기본값 |
    | **연관된 개념 ID (`concept_id`)** | `uuid` | FK, CASCADE |
    | **출처 종류 (`source_kind`)** | `text` | NOT NULL |
    | **문서/웹페이지 제목 (`title`)** | `text` |  |
    | **출처 URL (`url`)** | `text` |  |
    | **검증용 근거 발췌 (`snippet`)** | `text` |  |
    | **생성 일시 (`created_at`)** | `timestamptz` | NOT NULL, 기본값(now) |
    
    ### 개념 간 연결 관계 (`concept_edges`)
    
    | **컬럼명** | **데이터 타입** | **제약조건** |
    | --- | --- | --- |
    | **시작 개념 ID (`from_concept_id`)** | `uuid` | PK, FK, NOT NULL, CASCADE |
    | **도착 개념 ID (`to_concept_id`)** | `uuid` | PK, FK, NOT NULL, CASCADE |
    | **연결 종류 (`kind`)** | `edge_kind` | PK, NOT NULL |
    
    ### 챕터 (`chapters`)
    
    | **컬럼명** | **데이터 타입** | **제약조건** |
    | --- | --- | --- |
    | **챕터 고유 식별자 (`id`)** | `uuid` | PK, 기본값 |
    | **소속 코스 ID (`course_id`)** | `uuid` | FK, NOT NULL, CASCADE |
    | **챕터 순서 (`order_index`)** | `int` | NOT NULL |
    | **챕터 제목 (`title`)** | `text` | NOT NULL |
    | **챕터 출처 (`origin`)** | `chapter_origin` | NOT NULL, 기본값('book') |
    | **JIT 생성 트리거 상태 (`gen_status`)** | `gen_status` | NOT NULL, 기본값('pending') |
    
    ### 섹션/절 (`sections`)
    
    | **컬럼명** | **데이터 타입** | **제약조건** |
    | --- | --- | --- |
    | **섹션 고유 식별자 (`id`)** | `uuid` | PK, 기본값 |
    | **소속 챕터 ID (`chapter_id`)** | `uuid` | FK, NOT NULL, CASCADE |
    | **매핑된 개념 ID (`concept_id`)** | `uuid` | FK |
    | **섹션 순서 (`order_index`)** | `int` | NOT NULL |
    | **섹션 제목 (`title`)** | `text` | NOT NULL |
    
    ### 컴포넌트 블록 (`blocks`)
    
    | **컬럼명** | **데이터 타입** | **제약조건** |
    | --- | --- | --- |
    | **블록 고유 식별자 (`id`)** | `uuid` | PK, 기본값 |
    | **소속 섹션 ID (`section_id`)** | `uuid` | FK, CASCADE |
    | **블록 순서 (`order_index`)** | `int` | NOT NULL, 기본값(0) |
    | **블록 타입 (`type`)** | `text` | NOT NULL |
    | **시도 종류 (`kind`)** | `attempt_kind` |  |
    | **연관 개념 ID (`concept_id`)** | `uuid` | FK |
    | **출처 (`source`)** | `content_source` | NOT NULL |
    | **정답 추적 대상 여부 (`tracked`)** | `boolean` | NOT NULL, 기본값(false) |
    | **(검증용) 문서 청크 ID 배열 (`source_chunk_ids`)** | `uuid[]` | NOT NULL, 기본값('{}') |
    | **(검증용) 외부 출처 ID 배열 (`external_ref_ids`)** | `uuid[]` | NOT NULL, 기본값('{}') |
    | **근거 대조 통과 여부 (`verified`)** | `boolean` | NOT NULL, 기본값(false) |
    | **블록 핵심 데이터 (`data`)** | `jsonb` | NOT NULL |
    | **메타 데이터 (`meta`)** | `jsonb` | NOT NULL, 기본값('{}') |
    
    ## ╔ B. 학습자 계층 ╗
    
    ### 수강 현황 및 진단 (`enrollments`)
    
    | **컬럼명** | **데이터 타입** | **제약조건** |
    | --- | --- | --- |
    | **사용자 ID (`user_id`)** | `uuid` | PK, FK, NOT NULL |
    | **코스 ID (`course_id`)** | `uuid` | PK, FK, NOT NULL |
    | **천장(목표) 개념 ID (`ceiling_concept`)** | `uuid` | FK |
    | **진단 결과 바닥 개념 ID (`floor_concept`)** | `uuid` | FK |
    | **바닥 발견 여부 (`floor_found`)** | `boolean` | NOT NULL, 기본값(false) |
    | **진단 진행 상태 (`diag_status`)** | `diag_status` | NOT NULL, 기본값('not_started') |
    | **진단 문항 수 (`diag_q_count`)** | `int` | NOT NULL, 기본값(0) |
    | **자가 보고 데이터 (`self_report`)** | `jsonb` |  |
    | **수강 시작 일시 (`created_at`)** | `timestamptz` | NOT NULL, 기본값(now) |
    
    ### 개념 숙련도 및 복습 스케줄 (`concept_mastery`)
    
    | **컬럼명** | **데이터 타입** | **제약조건** |
    | --- | --- | --- |
    | **사용자 ID (`user_id`)** | `uuid` | PK, FK, NOT NULL |
    | **개념 ID (`concept_id`)** | `uuid` | PK, FK, NOT NULL |
    | **숙련도 상태 (`status`)** | `mastery_status` | NOT NULL, 기본값('locked') |
    | **종합 강도 (`strength`)** | `real` | NOT NULL, 기본값(0) |
    | **서술 채점 결과 (`explanation_score`)** | `real` | NOT NULL, 기본값(0) |
    | **사용자 확신도 (`confidence`)** | `confidence_lvl` |  |
    | **SM-2 난이도 지수 (`ease`)** | `real` | NOT NULL, 기본값(2.5) |
    | **다음 복습 간격(일) (`interval_days`)** | `int` | NOT NULL, 기본값(0) |
    | **마지막 복습 일시 (`last_reviewed_at`)** | `timestamptz` |  |
    | **다음 복습 예정 일시 (`next_due_at`)** | `timestamptz` |  |
    
    ### 모든 학습 시도 이력 (`attempts`)
    
    | **컬럼명** | **데이터 타입** | **제약조건** |
    | --- | --- | --- |
    | **시도 이력 고유 식별자 (`id`)** | `uuid` | PK, 기본값 |
    | **사용자 ID (`user_id`)** | `uuid` | FK, NOT NULL |
    | **푼 블록 ID (`block_id`)** | `uuid` | FK |
    | **연관 개념 ID (`concept_id`)** | `uuid` | FK, NOT NULL |
    | **시도 종류 (`kind`)** | `attempt_kind` | NOT NULL |
    | **정답 여부 (`correct`)** | `boolean` |  |
    | **부분 점수 (`score`)** | `real` |  |
    | **사용자 입력값 (`user_input`)** | `jsonb` |  |
    | **서술 채점 피드백 (`feedback`)** | `jsonb` |  |
    | **메타 데이터 (`meta`)** | `jsonb` | NOT NULL, 기본값('{}') |
    | **시도 일시 (`created_at`)** | `timestamptz` | NOT NULL, 기본값(now) |
    
    ### 섹션 진행도 (`section_progress`)
    
    | **컬럼명** | **데이터 타입** | **제약조건** |
    | --- | --- | --- |
    | **사용자 ID (`user_id`)** | `uuid` | PK, FK, NOT NULL |
    | **섹션 ID (`section_id`)** | `uuid` | PK, FK, NOT NULL |
    | **진행 상태 (`status`)** | `progress_status` | NOT NULL, 기본값('not_started') |
    | **제공된 버전 형태 (`variant_served`)** | `serve_variant` |  |
    | **완료 일시 (`completed_at`)** | `timestamptz` |  |
    
    ## ╔ C. 결제 / 구독 ╗
    
    ### 요금제 (`plans`)
    
    | **컬럼명** | **데이터 타입** | **제약조건** |
    | --- | --- | --- |
    | **요금제 고유 식별자 (`id`)** | `uuid` | PK, 기본값 |
    | **등급 (`tier`)** | `plan_tier` | NOT NULL |
    | **요금제 이름 (`name`)** | `text` | NOT NULL |
    | **가격(센트) (`price_cents`)** | `int` | NOT NULL |
    | **결제 주기 (`interval`)** | `text` | NOT NULL, 기본값('month') |
    
    ### 구독 정보 (`subscriptions`)
    
    | **컬럼명** | **데이터 타입** | **제약조건** |
    | --- | --- | --- |
    | **구독 고유 식별자 (`id`)** | `uuid` | PK, 기본값 |
    | **사용자 ID (`user_id`)** | `uuid` | FK, NOT NULL |
    | **요금제 ID (`plan_id`)** | `uuid` | FK, NOT NULL |
    | **구독 상태 (`status`)** | `sub_status` | NOT NULL |
    | **현재 구독 종료 예정 일시 (`current_period_end`)** | `timestamptz` |  |
    | **결제 제공자 (`provider`)** | `text` |  |
    | **결제사 측 구독 ID (`provider_sub_id`)** | `text` |  |
    | **구독 생성 일시 (`created_at`)** | `timestamptz` | NOT NULL, 기본값(now) |
    
    ### 결제 내역 (`payments`)
    
    | **컬럼명** | **데이터 타입** | **제약조건** |
    | --- | --- | --- |
    | **결제 고유 식별자 (`id`)** | `uuid` | PK, 기본값 |
    | **사용자 ID (`user_id`)** | `uuid` | FK, NOT NULL |
    | **연관된 구독 ID (`subscription_id`)** | `uuid` | FK |
    | **결제 금액(센트) (`amount_cents`)** | `int` | NOT NULL |
    | **결제 상태 (`status`)** | `payment_status` | NOT NULL |
    | **결제사 측 결제 ID (`provider_payment_id`)** | `text` |  |
    | **결제 일시 (`created_at`)** | `timestamptz` | NOT NULL, 기본값(now) |
    
    ## ╔ D. 알림 ╗
    
    ### 알림 내역 (`notifications`)
    
    | **컬럼명** | **데이터 타입** | **제약조건** |
    | --- | --- | --- |
    | **알림 고유 식별자 (`id`)** | `uuid` | PK, 기본값 |
    | **수신 사용자 ID (`user_id`)** | `uuid` | FK, NOT NULL |
    | **알림 유형 (`type`)** | `notif_type` | NOT NULL |
    | **알림 제목 (`title`)** | `text` | NOT NULL |
    | **알림 본문 내용 (`body`)** | `text` |  |
    | **딥링크용 데이터 (`data`)** | `jsonb` |  |
    | **읽음 처리 일시 (`read_at`)** | `timestamptz` |  |
    | **알림 생성 일시 (`created_at`)** | `timestamptz` | NOT NULL, 기본값(now) |
    
    ### 푸시 토큰 (`push_tokens`)
    
    | **컬럼명** | **데이터 타입** | **제약조건** |
    | --- | --- | --- |
    | **식별자 (`id`)** | `uuid` | PK, 기본값 |
    | **사용자 ID (`user_id`)** | `uuid` | FK, NOT NULL |
    | **기기 푸시 토큰 (`token`)** | `text` | UNIQUE, NOT NULL |
    | **플랫폼 (`platform`)** | `text` | NOT NULL |
    | **토큰 등록 일시 (`created_at`)** | `timestamptz` | NOT NULL, 기본값(now) |

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

공통: `Authorization: Bearer <token>` · 에러 `{error:{code,message}}` · 목록 `?cursor=&limit=`

### 인증/유저

| M | 경로 | 용도 |
| --- | --- | --- |
| GET | /auth/{provider}/login | 소셜 로그인 시작 — 구글/네이버 동의 화면으로 리다이렉트 (`{provider}`=google\|naver) |
| GET | /auth/{provider}/callback | 콜백: 코드 교환 → 유저 생성/조회 → 세션·토큰 발급 (신규면 프로필 설정으로) |
| POST | /auth/refresh | accessToken 갱신 |
| POST | /auth/logout 🔒 | 로그아웃 |
| GET | /me 🔒 | 내 정보 |
| PATCH | /me 🔒 | 프로필 수정(닉네임 등) |
| GET | /me/stats 🔒 | 대시보드 통계(streak/시간/목표율) |

### 자료/코스

| M | 경로 | 용도 |
| --- | --- | --- |
| POST | /documents 🔒 | 업로드 → {documentId, status} |
| GET | /documents/:id 🔒 | 처리 상태 폴링 |
| GET | /courses 🔒 | 내 책장 — 코스별 진행률 + `lastActivityAt`(=`MAX(attempts.created_at)`, 저장 아닌 계산값) 포함 |
| GET | /courses/:id 🔒 | 챕터/절 트리 |
| GET | /courses/:id/map 🔒 | 전체 지도(개념 그래프) |
| DELETE | /courses/:id 🔒 | 삭제 |

### 진단/생성/학습

| M | 경로 | 용도 |
| --- | --- | --- |
| POST | /courses/:id/diagnostic 🔒 | 진단 시작 → {next(블록 봉투)} (enrollments.diag_* 갱신) |
| POST | /courses/:id/diagnostic/answer 🔒 | 응답 → attempts(diagnostic) 기록 → 다음/종료(floor, ceiling) |
| POST | /chapters/:id/generate 🔒 | JIT 생성 트리거(생성+검증, 선행은 외부 근거 검색) |
| GET | /chapters/:id 🔒 | 생성 상태 폴링(gen_status) |
| POST | /sections/:id/confidence 🔒 | 확신도 → variant |
| GET | /sections/:id 🔒 | 절 블록 로드(verified 봉투[], 출처 배지 포함) |

### 인출/진행/복습/연결

| M | 경로 | 용도 |
| --- | --- | --- |
| POST | /attempts 🔒 | 정답 기록. explainBack이면 {score, feedback, missedPoints} 반환 |
| GET | /courses/:id/progress 🔒 | 완료/잠금 계산 |
| GET | /courses/:id/mastery 🔒 | 개념별 숙련도(메타인지 분석) |
| GET | /review/due?courseId= 🔒 | 복습 도래 개념 + reviewGate |
| POST | /review/answer 🔒 | 복습 응답 → 간격 갱신(attempts kind=review) |
| GET | /review/schedule?courseId= 🔒 | 복습 캘린더 |
| GET | /courses/:id/connections 🔒 | 연결 퀴즈 소집 |

### 결제/구독

| M | 경로 | 용도 |
| --- | --- | --- |
| GET | /billing/plans | 요금제 목록 |
| GET | /me/subscription 🔒 | 내 구독 상태 |
| POST | /billing/checkout 🔒 | 결제 세션 생성 → {checkoutUrl} |
| POST | /billing/cancel 🔒 | 구독 취소 |
| POST | /billing/webhook | 프로바이더 웹훅(서명 검증, 인증X) |

### 알림

| M | 경로 | 용도 |
| --- | --- | --- |
| GET | /notifications 🔒 | 알림 목록 |
| POST | /notifications/:id/read 🔒 | 읽음 |
| POST | /notifications/read-all 🔒 | 전체 읽음 |
| POST | /me/push-tokens 🔒 | 기기 토큰 등록 |
| DELETE | /me/push-tokens/:id 🔒 | 토큰 해제 |

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

---

## 부록. 구현 전 확정 항목

- [ ]  41 type 공유 스키마 단일 소스 파이프라인 구축 (백·프론트·LLM 동시 공급)
- [ ]  Solar 임베딩 차원 확정 후 `doc_chunks.embedding` 마이그레이션
- [ ]  외부 근거 소스 확정(웹서치 제공자 / 표준 코퍼스 / 자체 선행 DB 중 무엇으로 시작할지)