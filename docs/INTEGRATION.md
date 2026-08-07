# integration 브랜치 — 팀 안내서

> 세 브랜치를 합쳐 **파싱 → 학습 → 문제은행이 한 줄로 이어지는** 브랜치.
> 2026-08-07 기준. 정리: 윤현석.

```
integration
  ├ seedParsec        2812be7   파싱 (박지성)
  ├ feat/curriculum   5fbcfd7   학습 커리큘럼 (윤현석)
  └ feat/quiz-create  70dcbb4   문제은행 (소민섭)
```

각자 브랜치는 그대로 두고 여기서 합친다. **`feat/problems`는 구형이라 안 넣었다.**

---

## 1. 5분 안에 띄우기

```bash
git clone <repo> && cd metalearn && git checkout integration
cp backend/.env.example backend/.env     # UPSTAGE_API_KEY 채우기
docker compose up -d --build
```

```
백엔드   http://localhost:8000/api/health   → {"status":"ok"}
프론트   http://localhost:5173
DB       localhost:5432  (postgres/dev, DB명 metalearn_v3)
```

확인:
```bash
docker compose exec backend uv run alembic current          # 0009 (head)
docker compose exec backend uv run --group dev pytest -q    # 263 passed
docker compose exec frontend pnpm exec tsc --noEmit         # 통과
```

⚠️ **테스트·tsc는 컨테이너에서 돌린다.** 호스트엔 의존성이 없다.

⚠️ **실제 교재는 저장소에 없다.** `backend/tests/fixtures/*.md`와 `*.tree.json`이
gitignore다(저작물). 클론하면 `sample_sdlc.tree.json`(합성 샘플) 하나뿐이다.
실물 교재는 따로 공유해야 한다 — **공유 방법 미정. 정해야 한다.**

---

## 2. 지금 어디까지 이어졌나

```
PDF 업로드 ──✅──> 파싱 ✅ ──┬─> 코스 ✅ ─> 진단 ✅ API ─> 학습 ✅  책장에 수업으로
            /create        └─> 문제은행 ✅ API ──❌──> 문제집 화면
                                                 부를 화면 없음(mock)
```

**백엔드는 한 바퀴가 돈다. 화면으로는 한 군데가 남았다.**

### 08-07에 이은 것 — 코스가 학습 화면에 닿았다

여태 학습 화면은 **자료 하나**만 봤다. 파일 3개를 올리면 책이 3권 떴고, 코스
층(`course_topics`·`concept_links`)이 만든 값은 부르는 화면이 없었다.

```
전       GET /api/curriculum/documents  →  파싱 문서 id만
지금     GET /api/curriculum/documents  →  파싱 문서 + **코스**(코스에 묶인 자료는 뺀다)
```

책장이 이 목록만 보므로 이 한 줄로 수업이 책 한 권이 된다. 프론트는 안 고쳤다 —
`/curriculum/:docId`가 문자열 id를 받고 코스 id도 UUID 문자열이라 그대로 열린다.

```
학습 화면이 처음으로 볼 수 있게 된 것
  · 자료 여러 개가 한 권으로 — 뼈대(PPT) 목차 순서에 본문(교재) 설명이 붙는다
  · 사용자가 고친 목차 (course_topics — 제목 변경·순서·합치기·쪼개기)
  · 보강 단원(origin=inserted)이 들어올 자리 — 24·27번이 채운다
```

⚠️ **목차는 화면에 도착하기 전에 확정돼 있다.** 보강 단원 삽입은 코스 층(진단
시점)에서 끝나고 학습 중에 목차가 늘어나지 않는다. `grouping`의 "목차는 고정"
원칙과 부딪히지 않는 이유가 이것이다.

실측 (필기 + 실기 요약노트):

```
코스 트리   뼈대 58,681자(조각 18/18) · 교재 76,839자(조각 21/21)  ← 자르지 않는다
학습 화면   목차 5 · 화면 132 · 원문 빈 화면 0
```

```
뼈대 100%     화면 132개 중 원문이 빈 화면 0개
교재 가용성   조각 21/21 · 76,839자 전부 API에 실린다
교재 활용     🔴 41% — 붙어야 할 화면 73곳 중 30곳만 붙는다
```

**교재는 100%가 목표가 아니다.** 뼈대(PPT)가 학습 범위고 교재는 그 흐름을
설명하는 재료라, 다 쓰일 필요는 없고 **필요할 때 꺼낼 수 있으면 된다.**
문제는 마지막 줄이다 — 아래 §4 참고.

### 실측 (실제 PDF 한 권, 254KB)

```
파싱   목차 4 · 조각 15 · 문장 317 · 개념 134 · 근거 100% · 미배정 0
학습   화면 43 · 원문없음 0 · 화면 생성 5.5초 · 채점 → 준비도 → 복습 큐
문제   from-parsing 213초 → 저장 3 · 폐기 55 · 세션 → 채점 → 근거 원문 반환
```

### ① 업로드 — 08-07에 이었다

책장 → **새로운 학습 시작하기** → `/create` 위저드. 위저드는 라우트까지 이미
있었고 없던 건 `POST /api/parsing/documents` 한 줄이었다.

```
파일 고름 → 그 자리에서 업로드(202 접수증) → 목표 고르는 동안 서버가 파싱
        → 책장에 "분석 중" 카드(2초 폴링, 단계 문구는 DocStatus 그대로)
        → ready → 책 카드로 바뀐다
```

- 대기 목록(문서 id + 파일명)은 localStorage에 남는다. 파이프라인이 분 단위라
  그 사이 새로고침이 실제로 일어난다. **진행 상태는 안 들고 있다** — 서버가 진실이다.
- 같은 파일을 다시 올리면 지문이 같아 재파싱이 없다(실측: 같은 id·ready 즉시).
- `role`은 안 보낸다. 서버가 user_documents에만 쓰는데 users 테이블이 없어 저장되지 않는다.
- 링크·텍스트 자료는 받는 문이 없어 위저드에서 뺐다.

curl로도 여전히 된다:
```bash
curl -X POST "http://localhost:8000/api/parsing/documents" -F "file=@교재.pdf"
# → 202 {"id": "...", "status": "pending"}  이후 GET /api/parsing/documents/{id} 로 폴링
```

**② 문제집 화면이 mock이다.** `/quiz`가 보여주는 "데이터 통신 128문항" 등은 전부
`pages/quiz/mock.ts`다. `submitAttempt`까지 mock에서 온다. 실 API는 아래 3번 참고.
코스를 만들 화면도 없다(`POST /api/courses`만 있고 목록 API가 없다).

---

## 3. 실제로 도는 API (39개)

⚠️ `docs/API.md`는 **2026-07-03 문서**라 피벗 전 설계다. 실제로 도는 건 이 표다.

### 파싱
```
POST   /api/parsing/documents                  업로드 → 백그라운드 파싱 (202)
GET    /api/parsing/documents/{id}             상태 폴링 (pending→…→ready)
GET    /api/parsing/documents/{id}/tree        목차·조각·개념·★문장 앵커
GET    /api/parsing/concepts/search            뜻으로 개념 검색 (문서 경계 넘음)
POST   /api/parsing/debug/*                    단계별 실행기 (개발용, 6개)
```
★ `tree`의 `segments[].sentences[]`는 08-07에 추가. 전엔 `sentence_count`만 있었다.

### 코스
```
POST   /api/courses                            생성
GET    /api/courses/{id}                       조회
GET    /api/courses/{id}/tree                  코스 트리 (다자료 개념 연결 포함)
GET    /api/courses/{id}/prereqs               선수 판정 (pass/gray/rejected)
GET    /api/courses/{id}/gaps                  끊긴 고리
GET    /api/courses/{id}/diagnostic            ★24 진단 화면 ①~④ (LLM 없음)
GET    /api/courses/{id}/diagnostic/cards      ★③ 카드 4장 (LLM 1콜)
PATCH  /api/courses/{id}/diagnostic            ★①③ 목표·기간·설명 형식
POST   /api/courses/{id}/diagnostic/subjects   ★④-1 과목 단위 답 → 펼칠 과목
POST   /api/courses/{id}/diagnostic/prereqs    ★④-2 펼친 과목의 항목별 답
GET    /api/courses/{id}/diagnostic/probes     ★⑤ 확인 문항 (오답만 생성)
POST   /api/courses/{id}/diagnostic/probes     ★⑤ 채점 → known 보정
```

### 학습 커리큘럼
```
GET    /api/curriculum/documents                          자료 + **코스** 목록 (자동 주입)
POST   /api/curriculum/documents/from-parsing/{doc_id}    명시 주입 (?refresh=true 재파싱 반영)
POST   /api/curriculum/documents/from-course/{course_id}  ★코스 주입 (?refresh=true 목차 변경 반영)
GET    /api/curriculum/documents/{doc_id}                 자료 개요
GET    /api/curriculum/documents/{doc_id}/chapters/{i}    목차 하나
GET    .../chapters/{i}/formative                         단원 평가
GET    .../sections/{sid}                                 화면 (설명·빈칸·객관식 생성)
POST   .../sections/{sid}/answer                          채점 → 숙련도 누적
GET    .../review?days=N                                  복습 큐 (days는 시연용 시계 이동)
POST   .../prewarm?limit=N                                미리 생성 (데모 cold start 방지)
```
채점 바디: `{correct, conceptKey, kind}` · `kind` ∈ `diagnostic|retrieval|review|formative`

### 문제은행
```
POST   /api/courses/{cid}/quiz/from-parsing/{did}?budget=N   ★파싱 문서로 은행 생성
POST   /api/courses/{cid}/quiz/generate                      파싱 JSON을 바디로 받는 구 경로
GET    /api/courses/{cid}/quiz                               문서·목차별 문항 수
POST   /api/courses/{cid}/quiz/session                       범위 골라 문항 받기(정답 제외)
POST   /api/quiz/attempts                                    채점 → 정답·해설·근거 원문
```

⚠️ **표기가 갈린다.** curriculum은 camelCase(`docId`·`sectionId`), quiz는
snake_case(`toc_index`·`course_id`). 프론트가 둘을 같이 쓰면 걸린다. **정해야 한다.**

---

## 4. 각자에게

### 박지성(파싱) — 🔴 seedParsec에도 고쳐야 하는 것 둘

integration에서만 고쳤다. 그쪽에서 새로 빌드하거나 볼륨을 지우면 **앱이 안 뜬다.**

1. **`python-multipart`가 pyproject에 없다.** 업로드 라우터가 `UploadFile`을 쓰는데
   FastAPI가 라우트 등록 때 검사해서 **import 단계에서 앱 전체가 죽는다.**
   기존 컨테이너에 예전에 깔린 것으로 가려져 있었다.
2. **compose가 `POSTGRES_DB: metalearn`인데 `DATABASE_URL`은 `metalearn_v3`다.**
   그 DB를 아무도 안 만들어서, 새 볼륨이면 `alembic upgrade head`가
   `database "metalearn_v3" does not exist`로 죽는다.

그리고 `GET /tree`에 `segments[].sentences[]`를 추가했다(문제은행이 근거 표시에
쓴다). `text`는 안 싣는다 — `content[char_start:char_end]`로 복원된다.

### 윤현석(학습) — 🔴 교재 설명이 붙어야 할 화면의 41%에만 붙는다

**손댄 건 코스를 여는 문 셋뿐이다.** `adapters/parsing_tree.py`·`grouping.py` 등
화면을 만드는 로직은 하나도 안 건드렸다.

| 파일 | 무엇 |
| --- | --- |
| `adapters/course_tree.py` | **신규.** 코스 트리 → Document. 겉껍데기만 맞추고 나머지는 `document_from_tree` 재사용 |
| `bridge.py` | `ingest_course`(async) · `ingest_course_stored`(동기) · `sync_courses` |
| `store.py` | `ingest_course_tree` |
| `router.py` | `/documents`가 코스도 준다(+ `async`) · `/documents/from-course/{id}` 신설 |

코스 트리는 **조각을 자르지 않고 통째로** 준다. 단원 하나에 뼈대 조각과 본문
조각이 함께 오고, 조각마다 `document_id`·`filename`·`role`(skeleton\|body)이 붙는다.
`segments`는 seq로 정렬하면 뼈대가 먼저 오도록 본문 seq를 1000 이상으로 밀어 뒀다.

**그런데 붙어야 할 자리의 절반에 안 붙는다.**

교재가 100% 쓰일 필요는 없다 — 뼈대(PPT)가 학습 범위고 교재는 그 흐름을
설명하는 재료다. 그래서 재는 기준은 "교재를 몇 % 썼나"가 아니라
**"붙어야 할 자리에 붙었나"**다.

```
뼈대 개념 397개 중 교재 설명이 연결된 것    112개
그 개념들이 들어간 화면                      73개
그중 교재 원문이 실제로 실린 화면            30개  = 41%
```

원인은 `grouping._source_for`다.

```python
excerpts = split_by_concepts(source, list(keys))
if not excerpts or any(not e.matched for e in excerpts):
    return ""      # 화면 개념 셋 중 하나만 못 찾아도 원문을 통째로 비운다
```

개념명이 **제목으로** 나온 자리에서만 뽑는다. 필기 개념명은 `상태 패턴`인데
교재엔 영문 표(`| State |`)로 있어서 안 걸린다. 요약노트처럼 제목 없이 표·목록으로
흐르는 자료는 제목 기반 매칭이 109개 중 17개밖에 안 걸렸다(실측).

한때 우리 쪽에서 개념명 언저리를 창으로 잘라 억지로 붙였으나 걷어냈다 —
**화면을 만드는 건 우리 층이 아니고**, 자르면 그쪽이 쓸 재료가 준다.
재료는 다 넘겼으니 쓰는 방법은 정해 주세요.

`source`는 📎 원문 표시만이 아니라 **설명·문항을 만드는 재료**이기도 하다
(`explanation.py`의 `<교재 원문 (참고)>`). 비면 개념 정의 한 줄로 설명을 쓰게 된다.

그리고 하나 더: **`section_id`에 자료 id가 안 들어간다**(`hash(chunk_id|개념명들)`).
코스와 그 뼈대 자료를 둘 다 열면 진도가 같은 키를 쓴다. 같은 내용이라 맞을 수도
있는데, 코스가 목차 순서를 바꾸면 `chunk_id`가 달라져 진도가 갈린다. 지금은 코스에
묶인 자료를 책장에서 빼서 둘을 동시에 못 열게 해 뒀다 — 회피지 해결이 아니다.

### 소민섭(문제은행) — 🔴 모델 결정이 필요하다

`solar.py`를 합치며 quiz 호출이 `solar-pro2`(하드코딩)에서 `solar-pro3`로 넘어갔고
**문항이 0개가 됐다.** 호출은 성공하고 응답도 온다 — 출력 형태가 다르다:

```
solar-pro2   ```json [ {...}, {...} ] ```   배열+코드펜스 → 파싱 4개
solar-pro3   {...}{...}                     객체 이어붙임 → 파싱 0개
```

QUIZ_TUNING의 실측이 전부 pro2 기준이라 **`QUIZ_CHAT_MODEL="solar-pro2"`로 못박아
뒀다**(`core/config.py`). pro3로 옮기려면 프롬프트·파서·품질 실측을 다시 해야 하니
판단해 주세요.

그 외:
- `ExaoneClient`가 `LLMClient` 추상 메서드 둘을 안 채워 **앱 전체가 안 떴다.**
  `generate_json`·`embed_batch`를 추상에서 내리고 기본 구현이 거절하게 바꿨다
  (심판 전용 모델에 임베딩 배치를 강제할 이유가 없다).
- `intake`가 **문장 앵커 0개를 오류 0·경고 0으로 통과**시키고 있었다
  (`if chunk.sentences and …`라 빈 배열이면 검사를 건너뜀). 하드 실패로 바꿨다.
- 파싱 tree → `ParsedDocument` 변환기를 `features/quiz/adapters/parsing_tree.py`에
  뒀다. QUIZ_INPUT.md 계약 그대로다.
- 🔴 **저장 3 / 폐기 55.** 사유 대부분이 "원문에서 근거 문장을 찾지 못함"으로
  **선별 단계**에서 걸린 것이다(개념 134 중 출제가능 90). 이번 연결이 만든 회귀는
  아니지만(pro2 단독 실행과 동일) 품질은 봐주셔야 합니다.
- `docs/WORKLOG.md`(문제은행)와 `docs/WORK_LOG.md`(학습)가 **한 글자 차이로 공존**한다.
  이름을 바꾸든 합치든 정하는 게 좋겠다.

### 프론트 — 🟡 진단 화면이 없다 (24번 API는 다 됐다)

백엔드는 붙었고 화면이 없다. 화면 다섯, 순서대로:

```
① 왜 배우나     PATCH /diagnostic  {goal, deadline_weeks}
② 분야 맞나     GET   /diagnostic 의 field 를 확인만 받는다
③ 카드 4장      GET   /diagnostic/cards → 넷 중 하나 → PATCH {style}
④ 선수 체크     POST  /diagnostic/subjects  (과목 단위)
                → 돌아온 expand 과목만 항목 펼침 → POST /diagnostic/prereqs
⑤ 확인 문항     GET   /diagnostic/probes → 채점은 POST 로
```

- **④가 두 단계다.** 항목을 전부 물으면 54개다. 과목으로 먼저 묻고 "들어봤다"인
  것만 펼치면 실측 7 + 23 = 30번이 된다.
- **⑤는 빈 목록일 수 있다.** 정답을 못 세운 항목은 문항을 안 낸다 — 그럼 이
  화면을 건너뛴다. 개수도 고정이 아니다(1~4).
- ⚠️ **③ 문구를 조심해야 한다.** "당신에게 맞는 학습법"이 아니라 **"어떤 설명이
  읽기 편한가"**다. 러닝 스타일 맞춤에 학습 효과 근거는 없다(Pashler 2008).
  이건 성취가 아니라 이탈을 막는 장치다.
- ②는 12.5 분야 판정의 **유일한 검증 창구**다. 자동으로 검증할 방법이 없다.

### 다 같이 정할 것

```
1. API 표기      camelCase(curriculum) vs snake_case(quiz)
2. 교재 공유     fixtures/*.md 가 gitignore라 실물이 로컬에만 있다
3. 다음 우선순위  문제집 실 API 연결 (업로드 화면은 08-07에 끝) — 코스 목록 API가 선행이다
4. 코스 만드는 화면  책장이 코스를 보여주긴 한다(08-07). 없는 건 **만드는 자리**다 —
                 `POST /api/courses`를 부를 UI와 코스 목록 API가 아직 없다
```

---

## 5. 병합에서 실제로 터진 것 — **전부 충돌 0건이었다**

같은 일을 다시 겪지 않도록 남긴다. git이 조용히 합쳐 놓고 의미가 죽은 자리들이다.

| 무엇 | 왜 충돌이 안 났나 | 증상 |
| --- | --- | --- |
| `@app.on_event("startup")` | 파싱이 `lifespan`을 추가, 다른 줄 | 커리큘럼 자료 0개. **에러 없음** |
| alembic 리비전 `0002` ×2 | 파일 이름이 달랐다 | `upgrade head` 거절 → quiz를 `0008`로 |
| `[dependency-groups]` ×2 | 서로 다른 줄에 각자 추가 | TOML 중복 테이블 → uv 사망 |
| `ExaoneClient` | 코드가 안 겹쳤다 | import 시점 TypeError → **앱 전체 사망** |
| `solar-pro2` → `pro3` | solar.py를 한쪽으로 골랐다 | quiz 문항 0개. 호출은 성공 |

⇒ **병합 후엔 반드시 띄워서 한 바퀴 돌린다.** diff가 깨끗한 것과 도는 것은 다르다.

---

## 6. 문서 지도

| 문서 | 무엇 | 담당 |
| --- | --- | --- |
| **INTEGRATION.md** | 지금 이 문서. 합쳐진 상태·실행·API·각자 할 일 | 공용 |
| [STATUS.md](STATUS.md) | **파싱이 뭘 주는지는 여기가 기준** — 항목별 완료/미완 | 박지성 |
| [PARSING_v3.md](PARSING_v3.md) · [PARSING_PLAN.md](PARSING_PLAN.md) | 파싱 설계 · 단계 계획 | 박지성 |
| [LEARNER_CONTRACT.md](LEARNER_CONTRACT.md) | 학습 계층 스키마·API·회의 안건 | 윤현석 |
| [WORK_LOG.md](WORK_LOG.md) | 학습 일지 (결정·뒤집은 판단·기각한 것) | 윤현석 |
| [QUIZ.md](QUIZ.md) · [QUIZ_INPUT.md](QUIZ_INPUT.md) | 문제은행 설계 · 입력 계약 | 소민섭 |
| [QUIZ_TUNING.md](QUIZ_TUNING.md) | 문항 품질 실측 1~12회차 | 소민섭 |
| [WORKLOG.md](WORKLOG.md) | 문제은행 일지 (⚠️ 위 `WORK_LOG.md`와 다른 파일) | 소민섭 |
| [README.md](README.md) | docs 문서 지도 | 공용 |

⚠️ **믿지 말 것**: `API.md` · `SCHEMA.md` · `folder.md`는 **2026-07-03** 문서다.
7/28 피벗과 8/3 확정안보다 앞선다. 네 브랜치 모두 같은 blob이고 아무도 안 고쳤다.
실제로 도는 API는 이 문서 3번, 실제 스키마는 `backend/alembic/versions/`가 정본이다.
