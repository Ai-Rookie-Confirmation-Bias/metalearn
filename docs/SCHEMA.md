# MetaLearn — DB 스키마 (PostgreSQL)

> ## ⚠️ 이 문서는 **2026-07-03** 기준이다 — 피벗 전 설계다
>
> `API.md`와 같은 사정이다. 아래 테이블 중 상당수는 존재하지 않고, 실제로 있는
> `doc_topics`·`doc_segments`·`segment_sentences`·`concepts`·`quiz_items` 등은 없다.
>
> **정본은 `backend/alembic/versions/`다** (0001~0008). 테이블 목록은
> `docker compose exec db psql -U postgres -d metalearn_v3 -c "\dt"`.
> 학습 계층이 앞으로 만들 테이블은 [LEARNER_CONTRACT.md §3](LEARNER_CONTRACT.md).
>
> 이 파일은 초기 설계 기록으로 남긴다. 새 테이블을 여기에 추가하지 말 것.

> README.md에서 분리. **스키마 변경은 이 파일에서 관리한다.**


- 스키마
    
    ```sql
    -- ── ENUMS ──────────────────────────────────────────────
    CREATE TYPE document_status AS ENUM ('processing','ready','failed');
    CREATE TYPE document_kind   AS ENUM ('textbook','slide','notes','exam','link','text');  -- 자료 형태
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
      storage_url text NOT NULL,                -- 파일=스토리지 URL / link=원본 URL
      kind document_kind,                       -- 자료 형태(교재/슬라이드/필기/기출/링크/텍스트)
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
    
    CREATE TABLE courses (                       -- 한 코스 = 여러 자료(course_documents로 연결)
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      user_id uuid NOT NULL REFERENCES users(id),
      title text NOT NULL, category text,
      created_at timestamptz NOT NULL DEFAULT now()
    );

    -- 코스 ↔ 자료 (N:N). 메인/보조 역할 + 분할 자료(PPT 1~10장) 순서.
    CREATE TABLE course_documents (
      course_id   uuid NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
      document_id uuid NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
      role        text NOT NULL DEFAULT 'primary',   -- 'primary'(메인=천장 기준) | 'supplementary'(보조)
      order_index int  NOT NULL DEFAULT 0,           -- 분할 메인 순서
      PRIMARY KEY (course_id, document_id)
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
      purpose text,                                   -- 학습 목표(intent): 'exam'|'career'|'culture'|'hobby'
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
    | **자료 형태 (`document_kind`)** | `textbook`, `slide`, `notes`, `exam`, `link`, `text` |
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
    | **저장소 URL (`storage_url`)** | `text` | NOT NULL (파일=스토리지 URL / link=원본 URL) |
    | **자료 형태 (`kind`)** | `document_kind` | 교재/슬라이드/필기/기출/링크/텍스트 |
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
    | **코스 소유자 ID (`user_id`)** | `uuid` | FK, NOT NULL |
    | **코스 제목 (`title`)** | `text` | NOT NULL |
    | **카테고리 (`category`)** | `text` |  |
    | **생성 일시 (`created_at`)** | `timestamptz` | NOT NULL, 기본값(now) |
    
    ### 코스-자료 연결 (`course_documents`)
    
    | **컬럼명** | **데이터 타입** | **제약조건** |
    | --- | --- | --- |
    | **코스 ID (`course_id`)** | `uuid` | PK, FK, NOT NULL, CASCADE |
    | **문서 ID (`document_id`)** | `uuid` | PK, FK, NOT NULL, CASCADE |
    | **역할 (`role`)** | `text` | NOT NULL, 기본값('primary') — primary(메인)/supplementary(보조) |
    | **정렬 순서 (`order_index`)** | `int` | NOT NULL, 기본값(0) — 분할 메인 순서 |
    
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
    | **학습 목표 intent (`purpose`)** | `text` | `exam`/`career`/`culture`/`hobby` |
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
