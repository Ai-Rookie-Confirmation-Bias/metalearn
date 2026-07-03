# 학습 서빙 파이프라인 구현 일지 (feat/backend-ai-core)

> 2026-07-03. dev 브랜치 스키마/기획(docs/SCHEMA.md, docs/API.md) 기준으로
> **"커리큘럼이 주어졌을 때 → 학습 콘텐츠를 어떻게 만들고 → 프론트 봉투로 어떻게 내보낼지"**를 구현했다.
> 실제 Docker + PostgreSQL + Solar(solar-pro3)로 E2E 검증 완료.

---

## 1. 무엇을 만들었나 (한 줄)

**JIT 생성 → 근거 검증 → 봉투 서빙** 파이프라인:
씨앗이 만들어둔 커리큘럼(chapters/sections)을 입력으로, 챕터 진입 시 블록을 생성하고,
`verified=true`만, 확신도(variant)에 맞게, **정답을 스트립한 봉투**로 프론트에 내보낸다.

```
POST /api/chapters/:id/generate   JIT 생성 트리거 (멱등, 백그라운드)
GET  /api/chapters/:id            gen_status 폴링 (pending→generating→ready|failed)
POST /api/sections/:id/confidence 확신도(sure/ambiguous/unknown) → variant 결정·기록
GET  /api/sections/:id            절 블록 서빙 (verified만 + variant 필터 + 정답 스트립)
GET  /api/courses/:id             커리큘럼 트리 (챕터/절 + 학습자 진행/숙련도)
```

## 2. 새로 만든/수정한 파일

| 파일 | 역할 |
|---|---|
| `backend/app/features/learning/generator.py` | **[신규]** JIT 블록 생성기. 프롬프트 빌드 → LLM → JSON 파싱 → type별 Pydantic 코어스 → 검증 게이트. 순수 계층(DB 의존 없음) |
| `backend/app/features/learning/repository.py` | **[신규]** DB 접근. gen_status 원자 전이, 블록 교체 저장, 근거(청크/외부근거) 조회, 확신도/variant upsert |
| `backend/app/features/learning/serializer.py` | **[신규]** DB Block → 와이어 봉투. **정답 스트립 규칙 단일 관리** + variant 필터 |
| `backend/app/features/learning/service.py` | **[신규]** 유스케이스 오케스트레이션. 생성 트리거/백그라운드 실행, 확신도→variant, 절 서빙 |
| `backend/app/features/learning/router.py` | **[수정]** 위 4개 학습 엔드포인트 등록 |
| `backend/app/features/learning/schemas.py` | **[수정]** GenerateTrigger/ChapterStatus/Confidence DTO 추가 (봉투 DTO는 기존 것 사용) |
| `backend/app/features/curriculum/schemas.py` | **[신규]** 커리큘럼 트리 DTO (챕터/절 + 진행/숙련도) |
| `backend/app/features/curriculum/repository.py` | **[신규]** 트리 일괄 조회 (N+1 방지) |
| `backend/app/features/curriculum/router.py` | **[수정]** `GET /courses/:id` 구현 |
| `backend/app/core/deps.py` | **[신규]** 임시 유저 의존성 (`X-User-Id` 헤더, 없으면 dev UUID). auth 완성 시 JWT로 교체 |
| `backend/app/core/llm/mock.py` | **[수정]** 블록 생성 프롬프트(BLOCKS_JSON)에 유효 JSON 응답 — API 키 없이 E2E 가능 |
| `backend/app/models_registry.py` | **[신규]** 전체 ORM 모델 단일 임포트 지점 (FK 해석 버그 수정, 아래 §5) |
| `backend/app/main.py` | **[수정]** models_registry 임포트 |
| `backend/app/api.py` | **[수정]** learning/curriculum 라우터를 prefix 없이 등록 → docs/API.md 경로와 일치 |
| `backend/dev_seed_serving.py` | **[신규·임시]** 씨앗 완성 전까지 서빙을 테스트할 dev 픽스처 시드 (멱등) |

## 3. 어떤 생각으로 설계했나 (결정과 이유)

### 3-1. 생성기는 순수 계층으로 분리
`generator.py`는 DB/ORM을 모른다. 입력(개념+근거 발췌 DTO) → 출력(BlockDraft 리스트).
- **이유**: 팀원(parsing/seed)과 인터페이스가 겹치는 곳이라, DB 스키마가 흔들려도 생성 로직이 안 흔들리게. 유닛테스트도 LLM mock만 주입하면 됨.

### 3-2. 검증 게이트 — "근거 없으면 저장 자체를 안 한다"
기획서 §2.5A의 verified 불변식을 두 겹으로 강제:
- 생성 시: `can_mark_verified()` 통과 못 하면 **저장하지 않고 폐기** (서빙 금지보다 강한 정책 — dangling 자체를 안 만든다)
- 서빙 시: 쿼리가 `WHERE verified=true`만 조회 (이중 안전망)
- 비유(analogy)는 근거 면제, 대신 `label='비유'` 강제 (규칙대로)
- **현재 한계**: "근거 ID 존재" 게이트까지만. **사실문장 단위 faithfulness LLM 대조는 미구현(TODO)** — `generator._verify()` 내부만 교체하면 되는 구조로 자리를 파둠.

### 3-3. 정답 스트립 — 치팅 방지 (기획에 없던 걸 추가)
`blocks.data`에는 mcq `answerIndex`, cloze `blanks`, explainBack `rubric`이 들어있는데,
봉투를 그대로 내리면 개발자도구로 정답이 다 보인다. → `serializer.py`에서 **type별 스트립 규칙을 단일 관리**:
- mcq: `answerIndex`, `explanation` 제거
- cloze: `blanks` 제거 → `blanksCount`(입력칸 수)로 대체
- explainBack/reviewGate: `rubric` 제거
- **결과**: 정오 판정은 반드시 서버(POST /attempts)에서 하게 됨 — "판단은 서버" 원칙과 일치.
- ⚠️ **프론트 공유 필요**: 새 type 추가 시 `_STRIP_FIELDS`에 규칙 등록해야 함.

### 3-4. variant는 "부분집합(㉮)" 방식으로 잠정 구현
`blocks.variant` 컬럼 추가는 팀 미결이라, 스키마 변경 없는 부분집합 필터로 구현:
- `full` = 전부 / `compressed` = analogy 제외 / `quick` = tracked 문제만
- 확신도 매핑: `sure→quick`, `ambiguous→compressed`, `unknown→full`
- quick/compressed에서 블록이 0개가 되면 full로 안전 폴백
- **팀 결정(㉯ 별도 생성)이 나면 `serializer.filter_by_variant()`만 교체하면 된다.**

### 3-5. 생성 트리거 멱등성 — 새로고침 연타 방어
`UPDATE chapters SET gen_status='generating' WHERE id=? AND gen_status IN ('pending','failed')`
조건부 UPDATE 한 방으로 경합 차단. 이미 generating/ready면 현재 상태만 반환(재생성 없음).
재생성 경로는 failed → 재트리거만 허용.

### 3-6. JIT 개인화 입력
생성 시 `concept_mastery.strength`를 읽어 난이도 힌트(기초/표준/심화)를 프롬프트에 반영.
→ 진단이 끝난 유저일수록 생성물이 개인화됨. (같은 절이라도 A는 기초, B는 심화 문제가 생성됨)

### 3-7. LLM 실패 폴백 — 지어내지 않는 폴백
LLM 응답 파싱 실패(2회) 시, **근거 청크 원문을 그대로 인용**하는 concept + explainBack 폴백 블록 생성.
생성이 아니라 인용이므로 "근거 없이 지어낸 사실 금지" 원칙 위반이 아님.

## 4. E2E 검증 결과 (실환경: Docker + PostgreSQL + Solar solar-pro3)

`dev_seed_serving.py`로 픽스처(유저/문서/청크 3개/코스/개념 2개[book 1, ai_prereq 1]/챕터/절 2개) 시드 후:

| 검증 항목 | 결과 |
|---|---|
| `GET /courses/:id` 트리 (챕터/절 + 진행 필드) | ✅ |
| `POST /chapters/:id/generate` → generating | ✅ |
| 생성 중 재트리거 → 재생성 없이 상태만 반환 (멱등) | ✅ |
| 폴링 → ready, **실제 Solar로 5블록 생성** (concept/analogy/cloze/mcq/explainBack, 전부 verified + 청크 근거 부착) | ✅ |
| 정답 유출 검사: 응답에 answerIndex/blanks/rubric/explanation **없음** | ✅ NO_LEAK |
| `POST confidence {sure}` → `variant: quick` | ✅ |
| quick 서빙 → tracked 문제 3개만 (concept/analogy 제외됨) | ✅ |
| ai_prereq 절 → `externalRefs`에 인용 배지(제목/URL) 포함 | ✅ |

**발견·수정한 버그**: `concept_mastery` 쓰기 시 `NoReferencedTableError: users` —
SQLAlchemy는 임포트된 모델만 FK 해석 가능한데 요청 경로에 따라 auth User가 미임포트.
→ `app/models_registry.py`(전 모델 단일 임포트)를 만들어 main.py에서 로드. 해결 확인.

## 5. 직접 확인하는 방법

```bash
docker compose up -d   # 이미 떠 있으면 생략 (핫리로드로 반영됨)
docker compose exec -T backend uv run python dev_seed_serving.py  # 픽스처 시드(멱등, ID 출력)
# 출력된 ID로:
curl -s localhost:8000/api/courses/<COURSE_ID>
curl -s -X POST localhost:8000/api/chapters/<CHAPTER_ID>/generate
curl -s localhost:8000/api/chapters/<CHAPTER_ID>            # ready 될 때까지
curl -s -X POST localhost:8000/api/sections/<SECTION_ID>/confidence \
  -H 'Content-Type: application/json' -d '{"confidence":"sure"}'
curl -s localhost:8000/api/sections/<SECTION_ID>
# 유저 지정은 X-User-Id 헤더 (없으면 dev 유저 00000000-...-0001)
```

## 6. (2차) POST /attempts — 인출 루프 구현 (같은 날)

서빙에 이어 **학생이 답을 제출하는 쪽**을 구현. 이것으로 §7 인출 → §8 추적 루프가 닫힘.

### 추가/수정 파일
| 파일 | 역할 |
|---|---|
| `learning/grading.py` | **[신규]** 서버 채점. mcq/cloze는 정오 비교, explainBack은 **Solar rubric 항목별 O/X 판정**(점수를 LLM이 직접 만들지 않고 서버가 비율 계산 — 채점 일관성) + LLM 실패 시 키워드 매칭 폴백. 답안을 데이터로 격리해 프롬프트 인젝션 방어 |
| `learning/repository.py` | **[확장]** mastery 행 잠금(FOR UPDATE), attempts 집계(시도/통과/연속오답 — 컬럼 저장 없이 계산), attempt INSERT, 절 완료 판정 쿼리 |
| `learning/service.py` | **[확장]** `record_attempt`: 채점 → mastery 갱신(행 잠금) → SM-2 스케줄 → next_action 결정 → attempts 기록 → 절 완료 판정, 한 흐름 |
| `learning/schemas.py` | **[확장]** `NextActionOut`(advance/thin_pass/supplement/prerequisite), AttemptRequest에 `meta`(프론트 신호 통로: elapsedMs 등) |
| `learning/router.py` | **[확장]** `POST /api/attempts` |

### 설계 결정
- **클라이언트 correct는 무시** — 정답이 서빙에서 스트립되므로 채점은 서버만 가능. 요청의 correct 필드는 하위호환용으로 받고 버림.
- **시도수/연속오답을 컬럼에 저장하지 않음** — append-only attempts에서 매번 집계("파생값은 계산" 원칙). 연속 오답은 최근 시도를 역순 스캔.
- **SM-2 연결**: review는 항상 갱신, learn은 통과 시 초기 스케줄 잡기(§9).
- **next_action을 응답에 포함** — 프론트가 supplement(보충)/prerequisite(선행 삽입) 흐름으로 라우팅할 수 있는 신호. attempts.meta에도 기록(약점 추적).
- **절 완료 판정**: 절의 tracked 블록 전부 통과(정답 또는 score≥0.6) → section_progress completed.

### E2E 검증 (실제 Solar 채점 포함)
| 시나리오 | 결과 |
|---|---|
| mcq 오답 1회 → `supplement` 액션 | ✅ |
| mcq 연속 오답 2회 → `prerequisite` 액션 (막힘 감지) | ✅ |
| mcq 정답 → `advance`, strength 0→0.22, next_due_at 스케줄 생성 | ✅ |
| explainBack 서술 제출 → **Solar가 rubric 대조 채점**: score 0.333 + 놓친 포인트 2개 + 한국어 피드백 | ✅ |
| 치팅 방어: correct=true로 속이고 오답 제출 → 서버 판정 false | ✅ |
| 커리큘럼 트리에 progress: in_progress / mastery: learning / strength 반영 | ✅ |

## 7. 남은 일 (다음 액션 제안 순)

1. **선행 삽입(살아있는 커리큘럼)** — next_action의 `prerequisite` 액션을 받아 `chapters(origin='prereq')` 동적 삽입하는 실행부. order_index는 간격 방식(10,20,30)으로 이미 시드도 맞춰둠. **다음 1순위.**
2. **faithfulness 검증** — 생성된 사실문장 vs 근거 대조 (Solar 별도 콜). `generator._verify()` 교체.
3. **RAG 교체** — 지금 청크 선택은 키워드 매칭 + 앞청크 보충(MVP). pgvector 임베딩 유사도 검색으로.
4. **auth 교체** — `core/deps.py`의 임시 헤더 방식 → JWT. User 모델도 소셜 로그인 스키마(provider/provider_uid)로 마이그레이션 필요 (현재 email/password 구형).
5. **팀 합의 필요**: variant ㉮/㉯ 확정, 프론트와 스트립 규칙·`blanksCount`·`nextAction` 필드 공유, 41-type 공유 스키마 파이프라인.

## 8. 팀원(parsing/seed 담당)과의 인터페이스

서빙이 시작되려면 다음이 채워져 있으면 된다 (dev_seed_serving.py가 이 계약의 샘플):
- `concepts` (source: book|ai_prereq, depth_level)
- `chapters`/`sections` (order_index 간격 방식 권장, section.concept_id 연결)
- `doc_chunks` (book 개념의 생성 근거)
- `external_refs` (ai_prereq 개념의 생성 근거 — **없으면 해당 절은 블록 생성이 폐기됨**, 검증 게이트가 막음)
- (선택) `concept_mastery` 초기값 — 있으면 생성 난이도가 개인화됨
