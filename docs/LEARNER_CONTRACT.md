# 학습 계층 — 스키마 · API (담당 **윤현석**, `feat/curriculum`)

> 2026-08-06. **구현된 것만** 적는다. 세 브랜치의 실제 코드를 읽고 썼다.

⚠️ `docs/SCHEMA.md`·`docs/API.md`는 **2026-07-03** 문서다. 7/28 피벗과 8/3 서비스
확정보다 앞서고, 세 브랜치 어디에도 그대로 구현된 게 없다(seedParsec에 있는 것도
같은 7/03 파일이다). **참고만 하고 정본으로 쓰지 않는다.**

---

## 0. 지금 실제로 있는 것

### seedParsec — 자료·개념 층 (돈다)

```
documents · user_documents · doc_topics · doc_segments · segment_sentences
concepts · concept_segments · concept_edges · doc_figures · global_concepts
courses · course_documents · course_topics
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

### 파싱에 요청하는 것 — 없다. 하나만 확인.

`course_topics.origin`에 `inserted`(보강 **단원** 삽입)와 `plan`(skip/brief/deep)이
미리 잡혀 있는데(`STATUS.md` 27번 "자리는 있음"), **우리는 단원을 안 만든다.**

```
단원 삽입  ✗  목차 목록이 바뀌면 "목차는 고정, 설명·분량만 변경"이 깨진다
화면 삽입  ✓  1단원이 1.29 → 1.30. 목차는 그대로다
```

담는 개념도 이미 문서 안에 있는 것이라 없던 내용을 지어내지 않는다.
**`course_topics.origin='inserted'`는 우리가 안 쓴다** — 쓸지 말지는 회의 안건.
`plan`은 우리 `ChapterPlan.mode`와 같은 값(normal/brief≈compressed/deep)이라
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

### 3.3 `attempts` — ★ 문 하나로 모은다

**지금 `quiz_attempts`가 따로 있다. 그대로 두면 숙련도가 두 군데로 갈린다.**
문제은행에서 푼 것도 그 사람이 아는 것이라 같은 누적에 들어가야 한다.

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

1. **`attempts` 하나로 합칠 것인가** — 지금 `quiz_attempts`가 따로다. 안 합치면
   숙련도가 두 군데로 갈린다. 합친다면 `quiz_item_id`를 nullable로 두고 우리가
   생성한 문항은 NULL로 둔다(§3.3)
2. **배분을 누가 하는가** — `course_topics.plan`(파싱) vs `ChapterPlan.mode`(우리).
   같은 값인데 두 곳에 있다. 근거가 숙련도 누적이고 그 데이터는 우리에게만 있다
3. **`course_topics.origin='inserted'`** — 단원 삽입은 우리가 안 쓴다(§1).
   자리를 비워둘지 지울지
4. **`users` 테이블** — 없어서 세 브랜치가 다 FK 없이 `user_id`를 들고 있다

---

## 7. 아직 없는 것 (우리 쪽)

| | 상태 |
|---|---|
| **저장** | 인메모리. 백엔드 재시작하면 진도가 0으로 돌아간다. 이 문서가 그걸 붙이려는 것 |
| **진단** | 생성기도 화면도 없다. `diagnostic 0.5` 자리가 비어 있다 |
| **성향** | `build_lesson(profile_block=)` 자리는 뚫려 있는데 라우터가 늘 빈 값을 넘긴다 |
| **분량 배분** | `plan.mode`가 화면에 "설명을 늘렸습니다"라고 뜨는데 **설명은 안 바뀐다** |
| **실파싱 연결** | 파일 픽스처(`*.tree.json`)를 읽는다. tree API 어댑터는 있다 |
| **선수 데이터** | 파싱 선수 이름의 절반 넘게가 개념 목록에 없다(필기 122/339, 실기 211/404). 보충 화면 기능의 상한 |
