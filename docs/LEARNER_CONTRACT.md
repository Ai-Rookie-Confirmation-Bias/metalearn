# 학습자 계층 — 스키마 · API (담당 **윤현석**, `feat/curriculum`)

`SCHEMA.md`의 층 나눔을 그대로 따른다. **A는 안 건드린다.**

```
A. 콘텐츠 + 개념 그래프    documents · chapters · sections · concepts · blocks   ← 파싱 담당
B. 학습자 계층             mastery · attempts · progress · enrollments           ← 이 문서
```

접점은 하나다: **"화면(section) 하나가 무엇인가."** 아래 §0만 합의되면 나머지는 붙는다.

⚠️ 지금 `SCHEMA.md`의 B 계층은 **구현 전에 쓰인 것**이라 실제와 다섯 군데가 어긋난다.
아래는 구현된 것을 기준으로 다시 쓴 판이다.

---

## 0. A 계층에 요청하는 것 (딱 두 개)

### ① `sections`가 개념과 1:1이면 안 된다

```sql
-- 지금
CREATE TABLE sections (          -- 절(학습·추적 단위, 개념과 1:1)
  concept_id uuid REFERENCES concepts(id),
  ...
);
```

우리 학습 화면은 **개념 2~4개짜리 슬라이스**다(`SCREEN_SIZE=3`). 진도·잠금·복습·
보충이 전부 이 단위로 돈다. 1:1이면 B 계층 전체가 안 맞는다.

```sql
-- 요청
CREATE TABLE sections (
  id uuid PRIMARY KEY,
  chapter_id uuid NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
  order_index int NOT NULL,
  title text NOT NULL,
  origin text NOT NULL DEFAULT 'book',   -- ② 참조
  page text,                             -- 📖 인용 표시
  source text                            -- 이 화면 개념들의 원문 구간
);
CREATE TABLE section_concepts (          -- 화면 ↔ 개념 N:M
  section_id uuid REFERENCES sections(id) ON DELETE CASCADE,
  concept_id uuid REFERENCES concepts(id),
  order_index int NOT NULL,
  PRIMARY KEY (section_id, concept_id)
);
```

### ② 삽입 자리를 **단원이 아니라 화면**에 둔다

```sql
-- 지금:  chapter_origin ENUM('book','prereq')  가 chapters 에 있고 sections 에는 없다
-- 요청:  정확히 반대
```

**단원은 새로 만들지 않는다.** 목차 목록이 바뀌면 "목차는 고정, 설명·분량만 변경"이라는
서비스 정의가 깨진다(파싱 `origin: inserted` 제안을 이래서 거절했다).

**화면은 만든다.** 반복해서 틀린 선수 개념이 있으면 그 화면 **앞에** 보충 화면을 끼운다.
1단원이 1.29 → 1.30이 되는 건 목차가 안 바뀐 것이고, 담는 개념도 이미 문서 안에 있다.

```
sections.origin = 'book'      파싱이 준 원래 화면
                | 'inserted'  우리가 끼운 보충 화면   ← 진도 분모에서 빠진다(§2)
```

---

## 1. 바뀐 전제 넷 (B 계층 설계의 근거)

| | 내용 |
|---|---|
| **누적 단위는 화면** | 개념이 아니다. 한 화면에 개념 2~4개가 같이 있고, 학습·인출·복습이 그 묶음으로 일어난다 |
| **네 출처가 하나로** | 진단 0.5 · 인출 1.0 · 복습 1.5 · 형성 2.0. 한 문항이 담는 정보량이 달라 가중한다 |
| **잠금은 평가에만, 진도로만** | 학습은 안 잠근다(integration이 잠갔다가 이탈). 이해도로 잠그면 못 하는 사람일수록 확인 기회를 잃는다 |
| **계산되는 값은 저장하지 않는다** | `recall`·`readiness`·`progress`는 파생값이다. §3 참조 |

---

## 2. B 계층 스키마 (구현 기준)

### 2.1 `section_mastery` — ★ 네 출처가 모이는 자리

`concept_mastery`를 대체하지 않고 **위에 얹는다.** 개념별 숙련도는 메타인지 분석에
그대로 쓰고, 학습 루프(진도·잠금·복습)는 화면 단위로 돈다.

```sql
CREATE TABLE section_mastery (
  user_id    uuid NOT NULL REFERENCES users(id),
  section_id uuid NOT NULL REFERENCES sections(id) ON DELETE CASCADE,

  attempts int  NOT NULL DEFAULT 0,      -- 표시용 문항 수
  weight   real NOT NULL DEFAULT 0,      -- ★ 출처 가중 합. **판정할 자격**을 본다
  score    real NOT NULL DEFAULT 0,      -- 가중 정답 합.  이해도 = score / weight

  streak       int NOT NULL DEFAULT 0,   -- ★ 연속 정답. 이게 없으면 복습 간격이 안 벌어진다
  last_success timestamptz,              -- ★ 망각곡선의 기준점. 없으면 복습 대상이 아니다

  by_kind          jsonb NOT NULL DEFAULT '{}'::jsonb,  -- {"diagnostic":2,"retrieval":5}
  wrong_by_concept jsonb NOT NULL DEFAULT '{}'::jsonb,  -- {"응집도":3} → 약점·보충의 근거
  recent           boolean[] NOT NULL DEFAULT '{}',     -- 최근 5개. "나아지는 중"

  PRIMARY KEY (user_id, section_id)
);
CREATE INDEX ON section_mastery (user_id, last_success);
```

**`weight`가 왜 따로 있나** — 한 문제 틀렸다고 "이해도 0%"라고 말하면 거짓말이다.
`weight >= 3.0` 이 되기 전에는 판정하지 않는다(실측 사고 후 만든 가드).

**`streak`가 왜 필요한가** — 복습 간격이 연속 정답으로 벌어진다. 이 컬럼이 없으면
망각곡선이 고정 간격이 된다.

```
연속정답   0     1     2     3      4      5
반감기    3.0일  5.4   9.7  17.5   31.5   56.7      (3.0 × 1.8^streak, 최대 5)
복습 시점 2.2일  4.0   7.2  12.9   23.2   41.8      (회상 0.6 아래로 내려올 때)
```

### 2.2 `attempts` — 세 군데 고친다

```sql
CREATE TYPE attempt_kind AS ENUM ('diagnostic','retrieval','review','formative');
--                                              ^^^^^^^^^          ^^^^^^^^^
--  learn      → retrieval  (인출학습. "읽었다"가 아니라 "꺼냈다"는 뜻이라 이름이 중요하다)
--  connection → formative  (단원 평가. 우리 누적에서 가중이 제일 높은 출처인데 자리가 없었다)

ALTER TABLE attempts
  ADD COLUMN section_id uuid REFERENCES sections(id),   -- ★ 기록 대상은 화면이다
  ALTER COLUMN concept_id DROP NOT NULL;                -- ★ 아래 참조
```

⚠️ **`concept_id`는 NULL이어야 한다.** 개념이 하나로 특정될 때만 그 개념에 붙인다.

- 객관식은 개념 여럿을 구별하는 문항이라 첫 개념에 몰아주면 **약점 통계가 통째로 거짓**이 된다
  (실측: 객관식 5/5가 오귀속이었고 그게 다음 목차 설명까지 오염시켰다)
- 성질 유형 빈칸은 답이 개념명이 아니라 라벨 개념에 붙일 근거가 약하다

**틀린 통계는 없는 통계보다 나쁘다.** 못 정하면 화면 단위로만 센다.

⚠️ **형성평가는 문항이 화면을 가로지른다.** 그래서 `section_id`를 **백엔드가 정해서**
내려보낸다(정답 개념을 가진 화면). 프론트가 고르게 두면 화면이 판단을 하게 된다.

### 2.3 `section_progress` — 그대로 두되 의미만 고정

진도는 `section_mastery.attempts > 0` 으로 충분해서 지금은 안 쓴다.
쓰게 되면 **`origin='inserted'`는 분모에서 뺀다.**

```
sections_total   origin='book' 인 화면만        ← 분모. 보충을 끼워도 안 움직인다
sections_extra   origin='inserted'             ← 따로 센다
```

안 그러면 `29화면 중 18개 = 62%` 가 `32화면 중 18개 = 56%` 가 되어
**열려 있던 단원 평가가 다시 잠긴다.** 학습을 했는데 벌을 받는 그림이다.
이해도·복습은 반대로 보충도 똑같이 센다 — 거기서 푼 것도 실력이다.

### 2.4 안 만드는 테이블

| | 이유 |
|---|---|
| `next_due_at` 컬럼 | **파생값이다.** `last_success` + `streak`로 언제든 계산된다. 저장하면 곡선을 바꿀 때 전부 다시 써야 하고, 두 값이 어긋나는 순간을 만든다 |
| 복습 큐 테이블 | 같은 이유. `recall(now) < 0.6` 인 화면을 그때 고르면 된다 |
| 진단 전용 테이블 | 진단도 `attempts(kind='diagnostic')`로 들어온다. **네 출처가 같은 문을 지난다**는 게 설계의 핵심이다 |
| 보충 화면 테이블 | 규칙이 결정적이라(같은 상태 → 같은 결과) 읽을 때 계산한다. `section_id`는 `supp::{개념명}`으로 결정적으로 만들어 진도 기록이 붙는다 |

---

## 3. 저장하는 값 / 계산하는 값

이 구분이 흐려지면 두 값이 어긋나는 버그가 생긴다.

```
저장   attempts · weight · score · streak · last_success · by_kind · wrong_by_concept · recent

계산   이해도    = score / weight                       (시도한 화면만. 안 푼 건 0점 아님)
       회상      = 2^(-경과 / 반감기)                    반감기 = 3일 × 1.8^streak
       복습 대상 = last_success 있음 AND 회상 < 0.6      ★ 한 번도 못 맞힌 건 복습이 아니다
       진도      = 시도한 화면 / origin='book' 화면
       준비도    = 이해도 × 진도 × 회상                  ← 하나로 합쳐지는 값
```

**★ 한 번도 못 맞힌 화면은 복습 큐에 없다.** 잊은 게 아니라 아직 모르는 것이라
처방이 다르다 — 그건 보충 화면과 설명 안 ⚡가 맡는다.

**이해도는 망각으로 안 깎는다.** 준비도가 낮을 때 "잊은 것"인지 "아직 모르는 것"인지
가르려면 둘이 따로 있어야 한다.

---

## 4. API (구현 완료 · `/api/curriculum`)

경로는 붙일 때 팀 규칙에 맞추면 된다. **계약은 모양이다.**

| M | 경로 | 용도 | LLM |
| --- | --- | --- | --- |
| GET | `/documents` | 자료 목록 | – |
| GET | `/documents/{doc}` | 준비도 + 목차 목록 | – |
| GET | `/documents/{doc}/chapters/{i}` | 화면 목록 + 단원 평가 잠금 | – |
| GET | `/documents/{doc}/chapters/{i}/formative` | 단원 평가 | 1콜 |
| GET | `/documents/{doc}/sections/{id}` | 학습 화면(설명·비유·⚡·빈칸·객관식·원문) | 2~3콜 |
| GET | `/documents/{doc}/review?days=N` | 복습 큐 | 화면당 1콜 |
| POST | `/documents/{doc}/sections/{id}/answer` | ★ 시도 기록 — **네 출처가 전부 이 문** | – |

### 기록 (한 곳뿐이다)

```jsonc
POST .../sections/{sectionId}/answer
{ "correct": true, "conceptKey": "응집도", "kind": "retrieval" }
//                  ^ null 가능(§2.2)      ^ diagnostic|retrieval|review|formative

→ { "sectionId", "status", "statusLabel", "attempts", "improving", "recall",
    "chapterRatio", "chapterMode", "chapterReason",   // 목차 배분이 바뀌었는지
    "readiness", "understanding" }                    // 문서 전체 누적
```

**바뀐 값을 그 자리에서 돌려준다.** "학습 → 분석 → 커리큘럼 변경"이 화면에서 보여야
우리가 파는 게 증명된다.

### 잠금 판정은 서버에서 끝낸다

```jsonc
GET .../chapters/{i}
→ { ..., "formativeReady": false,
         "formativeReason": "단원 평가는 화면을 60% 이상 학습하면 열립니다. 17개 더 보시면 됩니다." }
```

문턱을 프론트에도 두면 규칙이 두 곳에 생기고 언젠가 갈라진다. 평가 엔드포인트를 불러
알아낼 수도 있지만 그러면 **목차를 열 때마다 문항 생성이 돈다.**

### 블록 (화면이 조립만 하도록)

```
concept  {text}                          설명 본문
analogy  {text, label}                   💡 비유
tie_in   {text, more, cloze, label}      ⚡ 지난 결손. more=펼침 본문, cloze=그 끝의 빈칸
cloze    {sentence, answer, accept[], kind}   accept = 인정 표기(`폭포수`도 정답)
mcq      {question, options[], answer, explanation, concept, sectionId}
```

`kind`(정의/상황/성질)는 **화면에 안 쓴다** — 다양성 측정용이다. 유형 라벨로 학습자를
가두지 않는다.

### 시연용 시계 이동

`GET /review?days=N`. 첫 복습이 2.2일 뒤라 발표에서 기다릴 수 없다.
**가짜 데이터가 아니라 진짜 곡선을 시간만 옮긴 것**이라 심사에서 그대로 설명할 수 있다.

---

## 5. 아직 없는 것 (알고 계셔야 할 것)

| | 상태 |
|---|---|
| **저장** | 인메모리다. 백엔드 재시작하면 진도가 0으로 돌아간다. 이 문서가 그걸 붙이려는 것 |
| **진단** | 생성기도 화면도 없다. `diagnostic 0.5` 자리는 비어 있다 |
| **성향** | `build_lesson(profile_block=)` 자리는 뚫려 있는데 라우터가 항상 빈 값을 넘긴다 |
| **분량 배분** | `plan.mode`가 화면에 "설명을 늘렸습니다"라고 뜨는데 **설명은 안 바뀐다** |
| **선수 데이터** | 파싱 선수 이름의 절반 넘게가 개념 목록에 없다(필기 122/339, 실기 211/404). 보충 화면 기능의 상한이 여기다 |
