# 파싱 개발 계획 — 13단계 체크리스트

> 기준 문서: [PARSING_v3.md](./PARSING_v3.md)
> 기존 코드 출처: `origin/feat/yoonhs-integration`
> 대상 브랜치: dev (seed/materials 모두 빈 스텁 — 사실상 백지)

**범례** — 📦 기존 그대로 · 🔧 기존 고쳐서 · 🆕 새로 만듦

---

## M0. 기반 — 파싱 전 단계가 전부 의존

### [ ] 0-1. config 확장 🔧

`backend/app/core/config.py`

현재 `UPSTAGE_API_KEY` · `SOLAR_BASE_URL` 뿐. 추가할 것:

```
SOLAR_CHAT_MODEL          생성·판정용
DOCUMENT_PARSE_MODEL      document-parse-*
SOLAR_EMBED_QUERY_MODEL   개념 임베딩
SOLAR_EMBED_PASSAGE_MODEL 조각 임베딩 (비대칭)
SOLAR_EMBED_DIM           pgvector 차원 — 실측 후 확정
EXAONE_*                  비전 호출용 (M3에서 사용)

EXTRACTION_SECTION_CHAR_BUDGET   조각 문자 예산 (기존 4000)
EXTRACTION_MAX_CONCURRENCY       추출 동시성 (기존 8)
EMBED_BATCH_SIZE                 (기존 64)
CONCEPT_DEDUP_SIM_THRESHOLD      즉시 병합 문턱 (기존 0.92)
DEDUP_CANDIDATE_SIM_THRESHOLD    LLM 판정 후보 하한 (기존 0.85)
DEDUP_MAX_PAIRS / JUDGE_BATCH    (기존 200 / 50)
TOPIC_MAX_COUNT                  목차 상한 (10)
```

**완료 기준** — `settings.` 로 전부 접근 가능

---

### [ ] 0-2. SolarClient 보강 🔧 ← 이거 없으면 아무것도 못 함

`backend/app/core/llm/solar.py` (현재 `generate`/`embed` 2개뿐)

integration 브랜치의 구현을 가져온다. 없는 것 5개:

| 추가 | 왜 |
| --- | --- |
| `parse_document()` | **PDF를 못 읽음.** `/document-digitization` 호출 |
| `generate_json()` | 개념 추출·목차 분류가 JSON을 받아야 함 |
| `embed_batch()` | 개념 200개를 하나씩 부르면 200콜 |
| `_post_retrying()` | 429·5xx 백오프. 없으면 파이프라인 전체가 죽음 |
| 공유 풀 + 세마포어 | 조각 40개 동시 호출하면 즉시 429 |

**완료 기준** — 실제 PDF 하나로 `parse_document()` 호출 성공, elements 반환 확인

---

### [ ] 0-3. 스키마 확정 🆕 ⭐ 여기서 실수하면 다 갈아엎어야 함

마이그레이션 1개로 테이블 9개.

| 테이블 | 핵심 컬럼 | 주의 |
| --- | --- | --- |
| `documents` | 지문(해시) · 형식 · 상태 · 파싱버전 · 공개범위 | **`user_id` 넣지 말 것** (공용) |
| `doc_topics` | 문서FK · 순서 · 제목 · 페이지범위 | |
| `doc_segments` | 문서FK · **목차FK** · 순서 · 마크다운 · 요소범위 · 페이지범위 · 임베딩 | |
| `segment_sentences` | 조각FK · 순서 · 텍스트 · offset | 앵커 |
| `concepts` | 문서FK · **소속목차FK(1)** · 이름 · 정의 · 전역키 · 임베딩 | |
| `concept_segments` | 개념FK · 조각FK · 문장앵커 | ⭐ **다대다** |
| `concept_edges` | from · to · kind | |
| `doc_figures` | 문서FK · 조각FK · 이미지 · 요소위치 · 페이지 · **context_text** · **needs_vision** · description | |
| `global_concepts` | 전역키 · 표준명 · 임베딩 | M3에서 채움 |

**소유는 별도 테이블로** — `user_documents(user_id, document_id, role)`

**완료 기준** — `alembic upgrade head` 통과, 9개 테이블 생성 확인

---

## M1. 최소 관통 — PDF 1개가 끝까지

> 품질보다 **관통**이 목표. 문장앵커·전역키·밀도·LLM정제는 M2로.

### [ ] 1. Document Parse 📦 `[API 호출]`

`adapters/document_parse.py`

**하는 일** — PDF 바이트 → 요소 배열. 판정 없음, 순수 호출.

**출처** — `solar.py::parse_document()`

**나오는 형태**
```
{id:2, category:"heading1", page:3, content:{markdown:"■ OSI 7계층"}}
{id:4, category:"figure",   page:3, base64_encoding:"iVBOR..."}
{id:7, category:"footer",   page:3, content:{markdown:"- 3 -"}}
```

**Solar 1회**

---

### [ ] 2. 그림 분리 🔧 `[순수 로직 + 판정]`

`figures.py`

**출처** — `service.py::_extract_figures()`

**기존 그대로** — base64 뽑아 `doc_figures`로, elements에선 `pop`
(JSONB에 수 MB 남기면 안 됨. mime은 매직 바이트 판별. 200바이트 미만은 노이즈로 버림)

**🔧 추가 2개 — 파싱에서 설명을 만들지 않는다. 준비만 한다.**

- **`context_text` 추출** (순수 로직, 공짜)
  그림 앞뒤 인접 요소의 원문. 기존은 절 생성 때마다 DB를 뒤졌는데(`get_figure_context`),
  요소 배열을 손에 든 지금 한 번에 계산해 저장한다.

- **`needs_vision` 플래그** (판정)
  ```
  주변 텍스트 N자 미만  → true
  캡션 없음             → true
  category == chart     → true
  그 외                 → false
  ```

> **왜 여기서 설명을 안 만드나** — 300p 교재면 그림 30~80개. 파싱 호출이 2배가 되는데
> 실제로 화면에 뜨는 건 10~20개뿐이다. 그리고 교재 그림은 대부분 주변 원문에 설명이
> 이미 있어 이미지를 볼 필요가 없다. 기존 팀도 같은 결론으로 ingest에서 뺐다.
> (`service.py` 주석: "그림 설명은 절 생성 시에 개별 생성한다 — ingest 단계에서 만들지 않는다")

**Solar 0회**

---

### [ ] 3. 정제 1층 — 규칙 📦 `[판정]`

`refine.py`

**출처** — `refinement.py::apply_rules()`

**판정 3개**

| 판정 | 기준 |
| --- | --- |
| `decoration` | header/footer/footnote **이면서** (2회 이상 반복 **또는** 20자 이하) |
| `toc` | `1. 소프트웨어 ……… 15` 정규식이 줄의 과반 |
| `copyright` | 저작권 키워드 3개 이상 동시 출현 |

**원칙** — 물리 삭제 금지. `removed=<사유>` 마킹만. 오판해도 마크만 떼면 복구.

**바뀌는 형태** — `{id:1, ..., removed:"toc"}`

**Solar 0회**

---

### [ ] 5. 조각 만들기 🔧 `[순수 로직]`

> 4번(LLM 정제 스캔)은 M2로 미룸. M1은 규칙 정제만으로 진행.

`segment.py`

**출처** — `sectioning.py::chunk_elements()`

**기존 규칙 그대로 좋음**
- 제목 요소가 경계
- 문자 예산까지 인접 묶음
- **요소는 절대 안 쪼갬** → 표·수식 원자성 구조적 보장
- 200자 미만 조각은 버림 (목차 스텁·파트 표지)
- `removed` 붙은 요소는 건너뜀

**🔧 삭제할 것** — **파트 경계 병합 금지 규칙**
(4단계에서 파트를 안 뽑으므로 불필요. `_MAX_REAL_PARTS=12` 같은 땜빵도 함께 제거)

**나오는 형태**
```
조각 #7
  본문: "■ OSI 7계층\n\nOSI 모델은...\n\n■ 데이터링크 계층\n..."
  요소범위 2~6 · 페이지 3~3
```

**Solar 0회**

---

### [ ] 6. 조각 임베딩 📦 `[API 호출]`

**출처** — `service.py::_embed_chunks()`
2000자 절단, 16개씩 배치, **passage 모델** (개념은 query 모델 — 비대칭)

**Solar ⌈조각수/16⌉회**

---

### [ ] 7. 목차 분류 🆕 ⭐ `[API 호출 + 검산]` ← 가장 중요, 완전 신규

`topics.py`

**기존 코드 없음.** 기존은 정제 스캔이 뽑은 파트를 챕터로 썼는데 방향이 반대다.

**하는 일**
1. 조각들의 제목·앞부분을 늘어놓음
2. 자료에 목차가 있으면 **그 항목을 라벨 후보로**
3. 없으면 **10개 이내 주제를 생성**하게 함
4. 각 조각이 어디 속하는지 **분류만** 시킴

**검산** ← 이게 핵심
```
조각 40개 → 목차별 합계 40개
안 맞으면 실패로 처리. 누락이 산술적으로 걸린다.
```

**원문은 한 글자도 안 건드림. 라벨만 붙임.**

**바뀌는 형태** — 조각에 `topic_id` 부여

**Solar 1~2회** (조각 많으면 배치)

**완료 기준** — 목차 10개 이하, 조각 수 보존, 미분류 0

---

### [ ] 8. 개념 추출 📦 `[API 호출]` ← 전체 비용의 80%

`concepts.py`

**출처** — `service.py::_extraction_prompt()` + `_extract_concepts()`
**프롬프트를 거의 그대로 가져온다.** 잘 만들어져 있음:
- "요약·압축하지 말고 **전부**" ← LLM이 뭉뚱그리는 습성 차단
- **수식 평문화 복원** — `x2+x` → `x^2+x` (Document Parse가 위첨자를 평문화함)
- 슬러그 동시 산출 (추가 비용 0)
- prerequisites는 문자열 아닌 **객체 배열** 강제 (형식 이탈 보정 validator 포함)

**🔧 삭제** — `section` 필드. 7번이 이미 목차를 정했으므로 불필요.

**나오는 형태**
```
조각 #7 →
  concepts: [ OSI 7계층      { prereq: [네트워크 프로토콜] },
              데이터링크 계층 { prereq: [물리 계층] } ]
```

**Solar = 조각 수** (동시성 8, 실패 시 1회 재시도)

---

### [ ] 9. 개념 임베딩 📦 `[API 호출]`

**출처** — `service.py::_embed_all()` · 64개씩 배치, query 모델

**Solar ⌈개념수/64⌉회**

---

### [ ] 11. 저장 🔧 `[순수 로직]`

> 10번(중복 판정)은 M2로. M1은 이름 정규화만으로 1차 합침.

`persist.py`

**출처** — `service.py::_persist_graph()` — **2-pass 구조를 그대로 가져온다**

```
1바퀴: 모든 조각의 본문 개념 먼저 등록 → source=book 확정
2바퀴: 그 다음에야 선수관계 연결 → 새로 생기는 것만 ai_prereq
```

**왜 2-pass인가** — 개념 X가 조각 A에선 본문 타겟, 조각 B에선 선수개념일 수 있다.
순서가 섞이면 X가 "교재 밖 보충"으로 잘못 낙인찍힌다.

**🔧 고칠 것** — `source_chunk_id` 단수 대신 **`concept_segments` 다대다**에 저장

**Solar 0회**

---

### [ ] M1-오케스트레이션 🆕

`service.py` — 파이프라인 실행 + 상태 전이
`router.py` — `POST /parse/documents` · `GET /parse/documents/{id}`

**상태** — `parsing → refining → segmenting → topics → extracting → ready` / `failed`

### ✅ M1 완료 기준

PDF 하나 올려서 **목차 · 조각 · 개념 · 선후관계**가 DB에 들어가고 조회 API로 나온다.

---

## M2. 품질 층

### [ ] 4. 정제 2층 — LLM 스캔 🔧 `[API 호출 + 판정]`

**출처** — `refinement.py::_scan_prompt / _sanitize_scan / apply_scan()`

기존은 3개를 물었다: ① 본문 시작 요소번호 ② 프로파일 ③ **파트 경계**

**🔧 ③을 버린다.** 파트 경계 판정이 가드레일 5개가 붙은 그 지점이고, 실패하면 챕터가
파일명 하나로 퇴화하던 곳이다. **7번 목차 분류가 대체한다.**

**남길 것** — ①만. 표지·인사말·구매안내를 걷어내는 용도.
가드레일도 2개만: 비율 상한(앞 25%), **서문 구간에 표·수식 있으면 기각**
(실측 사고: 미적분 '준비 학습'이 서문으로 오판돼 개념 80→49 급감)

**Solar 1회**

---

### [ ] 5-b. 문장 분리 + 앵커 🆕 `[순수 로직]`

조각 본문을 문장으로 쪼개고 각 문장에 앵커 ID + offset 부여.

**쓰이는 곳** — 북마크 · 드래그 · "교재 33p 이 문장" 근거 표시

**주의** — 한국어 문장 경계, 표·수식 내부는 쪼개지 않기

---

### [ ] 10. 개념 정리 — 중복 판정 🔧 `[로직 + 호출]`

**출처** — `_normalize_name()` · `_dedup_pass()` · `repository.find_similar_pairs()`

**3중 방어 (기존 그대로 좋음)**

| 단계 | 방식 | 실측 근거 (기존 주석) |
| --- | --- | --- |
| ① 이름 정규화 | 괄호·**공백 전부** 제거 + 소문자 | "일계도함수/일계 도함수"는 임베딩 0.75~0.81이라 문턱에 안 걸림 |
| ② 임베딩 최근접 | cosine ≥ 0.92 즉시 병합 | — |
| ③ LLM 배치 판정 | 0.85~0.92 후보쌍 50개씩 | **진짜 중복이 그 구간에 별개 개념과 섞여 분포**해 단일 문턱으로 분리 불가 |

③의 판정 기준도 프롬프트에 잘 정리돼 있음 —
같음: 띄어쓰기·약어(DRM)·동의어 / 다름: 상하위관계·인접개념(전위↔후위 순회)·**애매하면 다름**

**🔧 반드시 고칠 것 — 병합할 때 출처를 합친다**

현재 `merge_concepts()`는 **엣지만 이관하고 `source_chunk_id`는 drop과 함께 삭제**된다.
정규화가 6p·11p·15p에서 나와 개념 3개가 됐다가 1개로 합쳐지면 **6p만 남고 나머지가 사라진다.**
→ `concept_segments`에 **전부 누적**

**Solar ≤4회**

---

### [ ] 2-b. 그림 인라인 복원 🆕 `[순수 로직]`

조각의 요소범위 안에서 그림의 원래 위치를 찾아 본문 흐름에 꽂는다.
(데이터는 이미 다 있음 — `element_id` + `element_from/to`)

---

### [ ] 12. 밀도 · 커버리지 🆕 `[순수 판정]`

`density.py` — **기존 없음**

```
조각당 평균 글자수    PPT ~60자 / 교재 400~800자
커버리지             개념 붙은 조각 / 총 조각
미분류 조각 목록
→ 밀도 등급: 본문 가능 / 뼈대만
```

**쓰이는 곳** — "프리로드에서 설명을 당겨올까" 판단 스위치

**⚠️ 기준값은 실측 후 확정** (PPT·교재·논문 각각 돌려보고)

**Solar 0회**

### ✅ M2 완료 기준

- 개념 하나 집으면 원문 조각이 **전부** 딸려 나온다
- 문장 앵커로 "33p 이 문장"을 가리킬 수 있다
- PPT를 넣으면 "밀도 낮음 — 뼈대만"이 나온다

---

## M3. 확장

### [ ] 13. 전역 개념 사전 🔧 `[로직 + 호출]`

**출처** — `seed/service.py::_fill_keys()` (슬러그 생성 로직 재사용)
LLM에 UUID를 에코시키지 않고 **배치 로컬 번호**로 주고받는 처리도 그대로 가져올 것

**🔧 고칠 것** — 현재 슬러그는 **코스 안에서만 유니크**. 전역 사전에 붙여야
과목 넘어 매칭·프리로드 매칭이 된다.

**Solar ⌈개념수/80⌉회** (추출 때 이미 슬러그를 받으므로 대부분 폴백용)

---

### [ ] 2-c. 그림 설명 생성 — EXAONE 비전 🆕

**파싱 파이프라인 밖.** 배치 또는 온디맨드.

```
needs_vision = false  → 주변 원문(context_text)으로 설명 생성  ← 기존 방식
needs_vision = true   → EXAONE 비전으로 이미지를 실제로 봄
둘 다 → doc_figures.description에 캐싱 (재사용)
```

**EXAONE에 적합한 이유** — 실시간 아님(배치 가능) · 소수 그림만(5~10개) · 저위험(보조 설명)

---

### [ ] 기출 경로 🆕

문항 분해 → 개념 태깅 → **출제 프로파일**(빈도·난이도·유형 분포)
문항 원본은 개인 자료로만 보관, **출제하지 않음**

### [ ] 어댑터 추가 🆕

웹·위키 (`linkfetch.py` 참고 가능) · PPTX · DOCX

---

## 안 하는 것

닫힘/열림 판정 · 사슬형/나열형 판정 · 녹음 STT · 문제 생성 · 이해도 계산

---

## 호출 비용 요약

| 단계 | Solar |
| --- | --- |
| 1 Document Parse | 1 |
| 4 정제 스캔 | 1 |
| 6 조각 임베딩 | ~3 |
| 7 목차 분류 | 1~2 |
| **8 개념 추출** | **~40** ← 80% |
| 9 개념 임베딩 | ~3 |
| 10 중복 판정 | ~4 |
| 13 전역 키 | ~3 |
| **합계** | **~55** |

2·3·5·11·12는 호출 0.

---

## 결정 대기

- [ ] `documents` **공용** 확정? (스키마 전체를 가름 — M0 전에 결정)
- [ ] `SOLAR_EMBED_DIM` 실측값
- [ ] 목차 분류 프롬프트·배치 크기
- [ ] 밀도 등급 기준값
- [ ] 한국어 문장 분리 방식
