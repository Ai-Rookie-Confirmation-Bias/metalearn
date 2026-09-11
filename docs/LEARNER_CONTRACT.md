# 학습 계층 — 스키마 · API (담당 **윤현석**, `feat/curriculum`)

> 2026-08-06. **구현된 것만** 적는다. 세 브랜치의 실제 코드를 읽고 썼다.

### ⚠️ 어느 문서를 믿을 것인가

`docs/SCHEMA.md`는 **dev·seedParsec·quiz-create·우리 브랜치의 blob이 전부 같다**
(`0a421f72`, 2026-07-03). 넷 중 아무도 안 고쳤다는 뜻이다. `docs/API.md`도 같은
07-03 본문이고 quiz-create만 문제은행 9줄을 덧붙였다. 둘 다 7/28 피벗과 8/3 서비스
확정보다 앞선다. **참고만 하고 정본으로 쓰지 않는다.**

```
정본        코드 — 마이그레이션 · models.py · router.py
그다음      브랜치별 08-05 문서   파싱 STATUS.md · PARSING_v3.md
                                문제 QUIZ.md · QUIZ_INPUT.md · QUIZ_TUNING.md
안 믿는다   SCHEMA.md · API.md · folder.md  (전부 07-03, 네 브랜치 동일)
```

이 문서의 사실 서술은 전부 코드에서 읽은 것이고, 진척도(❌/⭕)만 `STATUS.md`를 인용한다.

---

## 0. 지금 실제로 있는 것

### seedParsec — 자료·개념 층 (돈다)

```
documents · user_documents · doc_topics · doc_segments · segment_sentences
concepts · concept_segments · concept_edges · doc_figures · global_concepts
courses · course_documents · course_topics
(+ learning_items — v1 시절 RAG 벡터 스텁. 경계와 무관하다)
```

API: `GET /api/parsing/documents/{id}/tree` · `GET /api/parsing/concepts/search`
· `POST /api/courses` · `GET /api/courses/{id}/gaps`

`STATUS.md` 기준 **A·B는 돌고 C는 뼈대만, D·E는 없다.**
그중 **28 설명·문제 만들기 / 29 풀고 채점 / 30 복습 스케줄이 전부 ❌** — 이 문서가 그것이다.

### feat/quiz-create — 문항 은행 (돈다)

```
quiz_items    (course_id, document_id, toc_index, type, concept_name, data, evidence, difficulty, verified)
quiz_attempts (user_id, quiz_item_id, correct, user_input)
```

API: `POST /courses/{id}/quiz/generate` · `GET /courses/{id}/quiz`
· `POST /courses/{id}/quiz/session` · `POST /quiz/attempts`

### feat/curriculum — 학습 루프 (돈다, **DB 없음**)

메모리 안에서만 산다. 이 문서가 그걸 테이블로 내리려는 것이다.

### 아직 아무 데도 없는 것

- **`users` 테이블** — `courses.user_id`가 FK 없이 떠 있다. 우리도 같은 처지다
- **`sections`(학습 화면)** — 어느 브랜치에도 없다. §1 참조
- **`review`** — quiz-create의 `review/router.py`는 빈 스텁이다

---

## 1. 경계 — 화면(section)은 **우리가 만든다**

이게 이 문서에서 제일 중요하다. 파싱은 **개념까지** 준다. 그걸 학습 단위로
묶는 건 우리다.

```
파싱  doc_topics → concepts (+ concept_edges 선후관계, evidence 근거)
                        ↓
우리  화면(section) = 개념 2~4개 슬라이스   ← grouping.py. 진도·잠금·복습의 단위
```

`STATUS.md`의 **21번 `lesson`(개념 묶기) ❌**가 이 자리다. 파싱이 안 만들기로 했고
우리가 만들고 있다. 그러니 `sections` 테이블도 우리 것이다.

### ★ 파싱에 요청하는 것 — 목차 목록을 바꾸지 말 것

`course_topics.origin` enum이 넷이다(`course/models.py`). 문제는 `inserted` 하나가
아니다.

```python
BOOK = "book"          # 자료의 목차에서 복사
INSERTED = "inserted"  # 진단 결과로 끼워 넣은 보강 단원 (책 밖 선수개념)
MERGED = "merged"      # 여러 단원을 합침    ← 목차 목록이 줄어든다
SPLIT = "split"        # 한 단원을 쪼갬      ← 목차 목록이 늘어난다
```

`STATUS.md` 27번이 "❌ (자리는 있음)"이라 **아직 아무도 안 쓴다.** 지금 정해야 한다.

```
단원 삽입·병합·분할  ✗  목차 목록이 바뀌면 "목차는 고정, 설명·분량만 변경"이 깨진다
화면 삽입            ✓  1단원이 1.29 → 1.30. 목차는 그대로다
```

⚠️ **`merged`/`split`은 `inserted`보다 위험하다.** 삽입은 목록을 늘리기만 하지만,
병합·분할은 **목록 자체를 재편한다.** 우리 `learn_sections.topic_id`가
`course_topics.id` FK라 단원이 합쳐지거나 쪼개지는 순간 **그 아래 화면과 진도가
통째로 떠내려간다.** 넷 중 `book`만 쓰기로 못 박아야 한다(회의 안건 3).

`plan`(normal/skip/brief/deep)은 우리 `ChapterPlan.mode`와 같은 값이라
**둘 중 하나만 남겨야 한다.** 우리 쪽은 숙련도 누적에서 나오고, 그 데이터가
우리에게만 있다.

---

## 2. 바뀐 전제 넷

| | 내용 |
|---|---|
| **누적 단위는 화면** | 개념이 아니다. 한 화면에 개념 2~4개가 있고 학습·인출·복습이 그 묶음으로 일어난다 |
| **네 출처가 하나로** | 진단 0.5 · 인출 1.0 · 복습 1.5 · 형성 2.0. 한 문항이 담는 정보량이 달라 가중한다 |
| **잠금은 평가에만, 진도로만** | 학습은 안 잠근다. 이해도로 잠그면 못 하는 사람일수록 확인 기회를 잃는다 |
| **계산되는 값은 저장하지 않는다** | `recall`·`readiness`·`progress`는 파생값이다. §4 참조 |

---

## 3. 스키마 (신규)

`user_id`는 `users`가 없어 FK를 안 건다 — `courses.user_id`와 같은 처지다.

### 3.1 `learn_sections` — 학습 화면

```sql
CREATE TABLE learn_sections (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  course_id   uuid NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
  topic_id    uuid NOT NULL REFERENCES course_topics(id) ON DELETE CASCADE,
  seq         int  NOT NULL,
  title       text NOT NULL,
  origin      text NOT NULL DEFAULT 'book',  -- book | inserted  ★ §1
  reason      text NOT NULL DEFAULT '',      -- ⚡ 왜 여기 있는지. 규칙이 쓴 문장 그대로
  page        text,                          -- 📖 조각 범위 (p.4-6)
  source      text,                          -- 이 화면 개념들의 원문 구간
  UNIQUE (topic_id, seq)
);

CREATE TABLE learn_section_concepts (
  section_id uuid REFERENCES learn_sections(id) ON DELETE CASCADE,
  concept_id uuid REFERENCES concepts(id),
  seq        int NOT NULL,
  PRIMARY KEY (section_id, concept_id)
);
```

⚠️ **화면은 코스 소유다**(문서가 아니라). 같은 책이라도 사람마다 코스가 다르고,
보충 화면이 사람마다 다르게 끼워지기 때문이다. `course_topics`가 문서 목차의
복사본인 것과 같은 이유다.

### 3.2 `section_mastery` — ★ 네 출처가 모이는 자리

```sql
CREATE TABLE section_mastery (
  user_id    uuid NOT NULL,
  section_id uuid NOT NULL REFERENCES learn_sections(id) ON DELETE CASCADE,

  attempts int  NOT NULL DEFAULT 0,   -- 표시용 문항 수
  weight   real NOT NULL DEFAULT 0,   -- ★ 출처 가중 합. **판정할 자격**을 본다
  score    real NOT NULL DEFAULT 0,   -- 가중 정답 합.  이해도 = score / weight

  streak       int NOT NULL DEFAULT 0, -- ★ 연속 정답. 없으면 복습 간격이 안 벌어진다
  last_success timestamptz,            -- ★ 망각곡선 기준점. 없으면 복습 대상이 아니다

  by_kind          jsonb NOT NULL DEFAULT '{}'::jsonb, -- {"diagnostic":2,"retrieval":5}
  wrong_by_concept jsonb NOT NULL DEFAULT '{}'::jsonb, -- {"응집도":3} → 약점·보충 근거
  recent           boolean[] NOT NULL DEFAULT '{}',    -- 최근 5개. "나아지는 중"

  PRIMARY KEY (user_id, section_id)
);
CREATE INDEX ON section_mastery (user_id, last_success);
```

**`weight`가 왜 따로 있나** — 한 문제 틀렸다고 "이해도 0%"라 하면 거짓말이다.
`weight >= 3.0` 전에는 판정하지 않는다(실측 사고 후 만든 가드).

**`streak`가 왜 필요한가** — 이 컬럼이 없으면 망각곡선이 고정 간격이 된다.

```
연속정답   0     1     2     3      4      5
반감기    3.0일  5.4   9.7  17.5   31.5   56.7     (3.0 × 1.8^streak, 최대 5)
복습 시점 2.2일  4.0   7.2  12.9   23.2   41.8     (회상 0.6 아래로 내려올 때)
```

### 3.3 `attempts` — 네 출처가 지나는 문

**우리 네 출처(진단·인출·복습·형성)는 이 표 하나로 들어온다.** 아래 DDL은 그것까지가
확정이다.

⚠️ **문제은행을 여기 넣는 것은 아직 제안이다.** `QUIZ.md` §7-③이 〈데이터 격리〉를
**확정안**으로 적어 뒀다 — *"풀이 기록은 학습(숙련도·커리큘럼)에 안 섞임 → 전용
테이블"*. 아래 `quiz_item_id` 컬럼은 **회의 안건 1이 통과해야** 의미가 있고,
그 전까지는 `quiz_attempts`가 따로 사는 게 현재 규칙이다.

우리 쪽 근거만 적어 둔다: 네 출처가 한 문을 지나야 누적이 성립하는데,
문제은행만 밖에 있으면 **그 사람이 아는 걸 알고도 안 세는 것**이 된다.

⚠️ 그리고 **`quiz_items`는 FK가 하나도 없는 섬이다**(`quiz/models.py`).

```python
course_id:    Mapped[uuid.UUID]   # FK 아님, 그냥 Uuid
document_id:  Mapped[uuid.UUID]   # FK 아님
toc_index:    Mapped[int]         # course_topics.seq 아님, 정수 인덱스
concept_name: Mapped[str | None]  # concepts.id 아님, 문자열
```

그래서 아래 `quiz_item_id` FK는 **`quiz_items`에 `concept_id`가 생긴다는 전제**에서만
성립한다. 이름으로 붙이면 안 된다 — `concept_name` → `concepts.normalized_name`
문자열 매칭은 우리가 인출 라벨 검증에서 이미 데인 자리다(포함 매칭 오폭 31%,
`'모듈' ⊂ '모듈화'` · `'WAS' ⊂ 'OWASP'`). **틀린 귀속은 없는 귀속보다 나쁘다.**
단원을 가리키는 키도 셋으로 갈려 있다 — 우리 `topic_id`(FK) · 문제은행
`course_id+document_id+toc_index` · 파싱 `course_topics.seq`.

```sql
CREATE TYPE attempt_kind AS ENUM ('diagnostic','retrieval','review','formative');

CREATE TABLE attempts (                 -- append-only
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id    uuid NOT NULL,
  section_id uuid REFERENCES learn_sections(id),  -- ★ 기록 대상은 화면
  concept_id uuid REFERENCES concepts(id),        -- ★ NULL 가능 — 아래
  quiz_item_id uuid REFERENCES quiz_items(id),    -- 문제은행에서 온 시도
  kind       attempt_kind NOT NULL,
  correct    boolean,
  user_input jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ON attempts (user_id, section_id, created_at);
```

⚠️ **`concept_id`는 NULL이어야 한다.** 개념이 하나로 특정될 때만 그 개념에 붙인다.

- 객관식은 개념 여럿을 구별하는 문항이라 첫 개념에 몰아주면 **약점 통계가 통째로
  거짓**이 된다 (실측: 객관식 5/5가 오귀속이었고 다음 목차 설명까지 오염됐다)
- 성질 유형 빈칸은 답이 개념명이 아니라 라벨 개념에 붙일 근거가 약하다

**틀린 통계는 없는 통계보다 나쁘다.** 못 정하면 화면 단위로만 센다.

⚠️ **형성평가 문항은 화면을 가로지른다.** 그래서 `section_id`를 **서버가 정해서**
내려보낸다(정답 개념을 가진 화면). 프론트가 고르게 두면 화면이 판단을 하게 된다.

### 3.4 생성물 캐시 (선택)

지금은 프로세스 메모리다. 재시작하면 날아가고 화면당 5~7초를 다시 쓴다.

```sql
CREATE TABLE lesson_cache (
  section_id uuid REFERENCES learn_sections(id) ON DELETE CASCADE,
  variant    text NOT NULL,        -- 성향+약점 조합 키. 다르면 다른 결과다
  blocks     jsonb NOT NULL,       -- §5 블록 배열
  meta       jsonb NOT NULL DEFAULT '{}'::jsonb,  -- covered/gap/levels 품질 지표
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (section_id, variant)
);
```

⚠️ **캐시가 아니라 사실상 저장이다.** 같은 화면을 다시 열었을 때 다른 글이 나오면
학습자가 자기가 뭘 읽었는지 알 수 없다.

### 3.5 안 만드는 것

| | 이유 |
|---|---|
| `next_due_at` | **파생값.** `last_success`+`streak`로 계산된다. 저장하면 곡선을 바꿀 때 전부 다시 써야 하고 두 값이 어긋나는 순간을 만든다 |
| 복습 큐 테이블 | 같은 이유. `recall(now) < 0.6`인 화면을 그때 고른다 |
| 진단 전용 테이블 | 진단도 `attempts(kind='diagnostic')`로 들어온다. **네 출처가 같은 문을 지난다**가 설계의 핵심 |
| 보충 화면 테이블 | 규칙이 결정적이라 읽을 때 계산해도 된다. 다만 진도 기록이 붙어야 해서 `learn_sections`에 `origin='inserted'`로 남긴다 |

---

## 4. 저장하는 값 / 계산하는 값

이 구분이 흐려지면 두 값이 어긋나는 버그가 생긴다.

```
저장   attempts · weight · score · streak · last_success · by_kind · wrong_by_concept · recent

계산   이해도    = score / weight                      (시도한 화면만. 안 푼 건 0점 아님)
       회상      = 2^(-경과 / 반감기)                   반감기 = 3일 × 1.8^streak
       복습 대상 = last_success 있음 AND 회상 < 0.6     ★ 한 번도 못 맞힌 건 복습이 아니다
       진도      = 시도한 화면 / origin='book' 화면     ★ 보충은 분모에서 뺀다
       준비도    = 이해도 × 진도 × 회상                 ← 하나로 합쳐지는 값
```

**★ 보충 화면을 분모에 넣으면 안 된다.** `29화면 중 18개=62%`가 `32중 18=56%`가 되어
열려 있던 단원 평가가 다시 잠긴다. 학습을 했는데 벌을 받는다.
이해도·복습은 반대로 보충도 똑같이 센다 — 거기서 푼 것도 실력이다.

**★ 한 번도 못 맞힌 화면은 복습 큐에 없다.** 잊은 게 아니라 아직 모르는 것이라
처방이 다르다 — 그건 보충 화면과 설명 안 ⚡가 맡는다.

**이해도는 망각으로 안 깎는다.** 준비도가 낮을 때 "잊은 것"인지 "아직 모르는 것"인지
가르려면 둘이 따로 있어야 한다.

---

## 5. API (구현 완료)

지금 경로는 `/api/curriculum/documents/{doc_id}/…`이다(코스 층 붙기 전 픽스처 기준).
**붙일 때 `/api/courses/{course_id}/…`로 옮긴다.** 계약은 경로가 아니라 모양이다.

| M | 경로 | 용도 | LLM |
| --- | --- | --- | --- |
| GET | `/{course}/learn` | 준비도 + 목차 목록 | – |
| GET | `/{course}/topics/{i}` | 화면 목록 + 단원 평가 잠금 | – |
| GET | `/{course}/topics/{i}/formative` | 단원 평가 | 1콜 |
| GET | `/{course}/sections/{id}` | 학습 화면(설명·비유·⚡·빈칸·객관식·원문) | 2~3콜 |
| GET | `/{course}/review?days=N` | 복습 큐 | 화면당 1콜 |
| POST | `/{course}/sections/{id}/answer` | ★ 시도 기록 — **네 출처가 전부 이 문** | – |
| POST | `/documents/from-parsing/{id}` | 파싱 ready 문서 → 학습 store | – |

### 기록

```jsonc
POST .../sections/{sectionId}/answer
{ "correct": true, "conceptKey": "응집도", "kind": "retrieval" }
//                  ^ null 가능(§3.3)     ^ diagnostic|retrieval|review|formative

→ { "sectionId", "status", "statusLabel", "attempts", "improving", "recall",
    "chapterRatio", "chapterMode", "chapterReason",   // 목차 배분이 바뀌었는지
    "readiness", "understanding" }                    // 문서 전체 누적
```

**바뀐 값을 그 자리에서 돌려준다.** "학습 → 분석 → 커리큘럼 변경"이 화면에서 보여야
우리가 파는 게 증명된다.

### 잠금 판정은 서버에서 끝낸다

```jsonc
GET .../topics/{i}
→ { ..., "formativeReady": false,
         "formativeReason": "단원 평가는 화면을 60% 이상 학습하면 열립니다. 17개 더 보시면 됩니다." }
```

문턱을 프론트에도 두면 규칙이 두 곳에 생기고 갈라진다. 평가 엔드포인트를 불러
알아낼 수도 있지만 그러면 **목차를 열 때마다 문항 생성이 돈다.**

### 블록 (화면은 조립만)

```
concept  {text}                              설명 본문
analogy  {text, label}                       💡 비유
tie_in   {text, more, cloze, label}          ⚡ 지난 결손. more=펼침 본문, cloze=그 끝 빈칸
cloze    {sentence, answer, accept[], kind}  accept = 인정 표기(`폭포수`도 정답)
mcq      {question, options[], answer, explanation, concept, sectionId}
```

`kind`(정의/상황/성질)는 **화면에 안 쓴다** — 다양성 측정용이다.

### 시연용 시계 이동

`GET /review?days=N`. 첫 복습이 2.2일 뒤라 발표에서 기다릴 수 없다.
**가짜 데이터가 아니라 진짜 곡선을 시간만 옮긴 것**이라 그대로 설명할 수 있다.

---

## 6. 회의 안건

1. ★ **문제 풀이를 숙련도에 넣을 것인가** — "합칠까요"가 아니라 **`QUIZ.md` §7-③
   〈데이터 격리〉를 뒤집는 건**이다. 저쪽은 *"풀이 기록은 학습(숙련도·커리큘럼)에
   안 섞임 → 전용 테이블"*을 **확정안**으로 적었고 모델 docstring에도 두 번 있다.
   우리 근거: 네 출처(진단·인출·복습·형성)가 **한 문을 지나야** 누적이 성립한다.
   문제은행만 밖에 있으면 그 사람이 아는 걸 알고도 안 세는 것이다.
   합친다면 전제 둘 — ① `quiz_items.concept_id` FK 신설(§3.3, 이름 매칭 금지)
   ② `quiz_item_id`는 nullable(우리가 만든 문항은 NULL) ·
   `quiz_attempts.user_id`는 지금 nullable인데 우리는 NOT NULL이라 이것도 정해야 한다
2. **배분을 누가 하는가** — `course_topics.plan`(파싱) vs `ChapterPlan.mode`(우리).
   같은 값인데 두 곳에 있다. 근거가 숙련도 누적이고 그 데이터는 우리에게만 있다
3. ★ **`course_topics.origin`을 `book`만 쓰기로 못 박기** — `inserted`뿐 아니라
   `merged`·`split`이 목차 목록을 재편한다(§1). 아직 아무도 안 쓰므로 지금이 싸다
4. **`users` 테이블** — 없어서 세 브랜치가 다 FK 없이 `user_id`를 들고 있다
5. **정본 문서** — `SCHEMA.md`가 네 브랜치 blob 동일(07-03)이다. 통합 전에 누가
   다시 쓸지, 아니면 브랜치별 문서(STATUS·QUIZ·이 문서)를 정본으로 둘지

---

## 7. 아직 없는 것 (우리 쪽)

| | 상태 |
|---|---|
| **저장** | JSON 스냅샷(`curriculum_progress.json`). 재시작해도 진도는 남는다. DB는 다음 |
| ~~**진단**~~ | 08-08에 채웠다. 생성기(박지성 24) + 화면 5단계. 다만 `diagnostic 0.5`가 실제로 쌓이려면 ⑤ 확인 문항까지 풀어야 한다 |
| **성향** | `CURRICULUM_PROFILE` fixture → `build_lesson`. 온보딩 UI는 아직 |
| **분량 배분** | `plan.mode` → `mode_block`이 설명 프롬프트에 붙는다 |
| **실파싱 연결** | `GET /documents`가 ready 문서를 sync · `POST .../from-parsing/{id}` · doc_id=파싱 UUID |
| **선수 데이터** | 파싱 선수 이름의 절반 넘게가 개념 목록에 없다(필기 122/339, 실기 211/404). 보충 화면 기능의 상한 |
| ~~**업로드 화면**~~ | 08-07에 채웠다. `/create`가 `POST /api/parsing/documents`를 부르고 책장이 "분석 중"으로 폴링한다 |
| ~~**메타인지 분석**~~ | 08-08에 채웠다(`GET /api/curriculum/analysis` + `/analysis`). 다만 실측 `byKind`는 아직 `{retrieval: 4}` 하나 — **화면은 생겼는데 4출처는 아직 안 찼다** |
| ~~**코스 만드는 자리**~~ | 08-08에 채웠다. `/create` → ready 뒤 `POST /api/courses` → 책장에 수업 한 권. `GET /api/courses` 목록도 있다 |
| ~~**문제집 화면**~~ | 08-08~09에 실 API로 이었다(`/quiz`). 학습 누적과 분리(확정안 §7-③). 생성은 15분이라 시연 전에 건다 |

### 2026-08-07 이후 상태

`integration` 브랜치에서 **파싱 → 학습이 실제로 이어졌다.** 실측은
[INTEGRATION.md §2](INTEGRATION.md) 참고 — 실제 PDF 한 권이 화면 43개가 되고
설명·빈칸 생성, 채점, 복습 큐까지 돈다.

문제은행도 붙었다(`features/quiz/adapters/parsing_tree.py` + `bridge.py`).
⚠️ 그 과정에서 `GET /parsing/…/tree`에 **문장 앵커(`segments[].sentences[]`)를
추가**했다 — 우리 어댑터는 안 쓰지만(원문은 조각 본문을 통째로 받는다) 파싱 응답이
커졌으니 알고 있을 것.

**확정안 §7-③ 데이터 격리는 그대로다.** 문제은행 풀이는 `quiz_attempts`에만 남고
우리 누적(진단·인출·복습·형성 넷)에 안 섞인다. 합치자는 건 §6 회의 안건이다.

### 2026-08-08 이후 상태 — 4출처가 **화면에는** 다 있다

진단 화면과 메타인지 분석 화면이 붙어서, 네 출처가 어디서 오는지 **보여줄 자리**는
전부 생겼다. 그런데 실측 `byKind`는 아직 `{retrieval: 4}` 하나다.

**이 구분을 흐리면 안 된다.** 화면이 생긴 것과 누적이 찬 것은 다르다. 분석 화면이
빈 출처를 감추지 않고 경고로 띄우는 게 그래서다 — 0을 숨기면 화면이 실제보다
튼튼해 보이고, 그건 이 문서가 하려는 말과 정반대다. 데모에서 4출처를 주장하려면
진단 ⑤까지 풀고 복습·형성까지 한 바퀴 돌린 계정이 필요하다.
