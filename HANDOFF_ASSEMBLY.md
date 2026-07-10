> ✅ **인계 완료 — 역사 문서.** 내용은 `feat/yoonhs-integration`에 통합됨(2026-07-10). 최신 온보딩은 `docs/DEV_GUIDE.md`.

# 병합 트라이얼 인계 문서 (parsing 팀원용)

> 작성: 2026-07-07 · 작성 브랜치: `trial/full-assembly` (yoonhs 측, backend-ai-core 하류 담당)
> **이 브랜치들은 "합의안(ISSUE-001 UUID 통일)대로 합치면 실제로 돌아간다"를 실증한 제안물입니다.**
> **바로 병합용 아님 — 리뷰 + 협의용.** 마이그레이션 스쿼시는 반드시 양측 동시 진행(단독 금지).

---

## 0. 30초 요약

- `feat/backend-ai-core`(우리 학습엔진, **UUID PK 정본**) + `feat/parsing`(당신 상류 파이프라인, Integer PK)를 **UUID로 통일해 합쳐봤고, 빈 DB에서 업로드→진단→씨앗→학습→복습 전 구간이 실제로 돕니다.**
- 두 브랜치:
  - **`trial/parsing-merge`** — 백엔드만 통합 (당신 코드 UUID 포팅 + 성능 튜닝). 순수 백엔드 검증용.
  - **`trial/full-assembly`** — 위 + 프론트(integration) 배선. 화면으로 도는 첫 수직 완주. (이 문서가 있는 브랜치)
- **팀원 브랜치(`feat/parsing`)는 한 줄도 안 건드렸습니다.** 전부 로컬 신규 브랜치에서 작업, `git show`로 읽기만 함.

---

## 1. ISSUE-001을 어떻게 풀었나 (핵심)

**정본 = UUID** (`dev/docs/SCHEMA.md` 근거). parsing의 Integer PK 코드를 UUID로 포팅했습니다. 알고리즘(정제·섹셔닝·개념추출·BKT·씨앗조립)은 **로직 무변경, 타입/모델/import만 교체**.

### 모델 필드 유니온 (우리 모델에 parsing 필드 흡수)
| 테이블 | 흡수한 컬럼 |
|---|---|
| `documents` | refined_elements(JSONB), profile, error, storage_url nullable화 |
| `doc_chunks` | element_from/to, heading, part_index |
| `concepts` | **embedding(halfvec 4096)**, source_anchor, source_chunk_id, created_at, key(잠정 nullable) |
| `concept_mastery` | session_id, answered_count, resolved, locked (세션별 mastery를 정본 user×concept에 흡수) |
| 신설 | diagnostic_sessions, diagnostic_questions (UUID PK) |

### 값/이름 규약 정합
- `concepts.source`: `document`→`book`, `llm`→`ai_prereq`
- `enrollments`: `floor_concept_id`→`floor_concept` (우리 이름 정본)
- **ISSUE-015 반영**: 청크 임베딩 `embed_batch(purpose="passage")`, 개념은 query (비대칭)

### 마이그레이션
- **스쿼시 안 함(단독 금지 준수).** parsing 계보 versions 12개는 이 트라이얼에서만 제거(이중 head 방지), 우리 계보 head 위에 `0015_parsing_contract_fields.py` 추가.
- **최종 병합 시 해야 할 것**: 양측 동시에 versions 전부 삭제 → 정본 UUID 통합 모델로 단일 `0001_initial` 재작성.

### int id 생성순 의존 대체
UUID엔 "생성 순서"가 없어서, parsing이 `id` 순서에 의존하던 곳(커리큘럼 트리·floor/ceiling·중복 dedup 타이브레이크)을 `(part_index, chunk_index)` 문서순 / `created_at`으로 교체. **리뷰 요망** — 원 의도와 같은지 확인 필요.

---

## 2. 🔴 최우선 확인 — 진단 서비스 이벤트 루프 데드락 (ISSUE-019)

**실사용 중 서버 전체 무응답(CPU 0%) 발생, `pg_terminate_backend`로 복구.**

- **위치**: `backend/app/features/diagnostic/service.py`
- **원인**: `start()`가 DB 트랜잭션을 연 채(session/enrollment/mastery 행 락 보유) `_ensure_questions`에서 LLM(`generate_json`)을 **여러 번 await**하고, `commit`은 맨 끝(`_build_state`)에 일어남. 이 사이 다른 요청의 동기 UPDATE(enrollments 등)가 락을 기다리면, sync SQLAlchemy가 이벤트 루프 스레드를 블록 → 전체 정지.
- **재현**: 문서 업로드(파싱 중)와 진단 start를 **동시** 실행.
- **제안 수정**: LLM 콜 진입 전에 커밋해 락을 놓거나(문항 생성 트랜잭션 분리), async 엔드포인트의 동기 DB를 threadpool로. **진단은 parsing 담당 영역이라 하드픽스 안 하고 남겨둠** — 협의 필요.
- 참고: 우리 학습 쪽 `record_attempt`는 같은 패턴 회피 완료 (LLM 채점을 행 락 **밖**에서 수행, docstring 명시). 대조 참고용.

---

## 3. 우리가 추가로 한 것 (리뷰 대상)

`trial/parsing-merge`에서 (백엔드):
- `perf(learning) 30f9977` — JIT 생성 병렬화(절 gather + faithfulness 동시판정 + json_mode + 커넥션풀). **E2E 34.5s→11.2s (3.1배)**. solar.py는 당신의 재시도 로직(Retry-After 존중) + 우리 공유풀/세마포어 **양쪽 장점 통합**.

`trial/full-assembly`에서 추가 (프론트 배선 + 진단 리스코핑):
- `305e38d` **진단 스코핑** — 팀 회의(2026-07-05) 결정 구현 **제안**: 전 개념 출제(191개) → **커리큘럼 앞부분 메인 4 + 선수 방향 2, 총 문항 캡 10**. config `DIAG_MAX_MAIN_CONCEPTS`/`DIAG_MAX_TOTAL_QUESTIONS`. ⚠️ **진단은 당신 영역** — 코드 주석에 "리뷰 대상" 명시. 회의 방향(가벼운 계단식 체크, 평가 스트레스 최소화)과 정합 목적.
- `84a7b09` 업로드→진단→씨앗→책장 프론트 배선 (신규 DiagnosisPage 포함)
- `0e1b3fd` 진단 진행률 표시를 문항 기준으로 (개념 수 오해 제거)
- `91b5d0b` analogy 블록 렌더러 (정본 41 컴포넌트 중 미구현분, registry 추가)
- `157416b` tracked 0개 절(비유만 있는 선행 절) 열람 완료 처리 — 진행 막힘 버그 해소

---

## 4. 검증 결과 (2026-07-07, 실행함)

빈 검증 DB(metalearn_verify)에서 회귀 **11/11 PASS**:
- alembic 0001→0015 전체 적용 ✅
- 시드 → placement → 챕터 생성 **8.1s**→ready ✅
- 봉투 정답 스트립 NO_LEAK ✅
- 서버 채점 + **치팅 방어**(correct=true 위조해도 서버가 4지선다 중 1개만 정답판정) ✅
- 진단 스코핑(수학 191개념 → 문항 6개) + 진행률 신필드 ✅
- 복습 due/schedule ✅ / read-complete 409(채점절 거부) ✅
- 프론트 tsc 통과 ✅ / import+configure_mappers ✅ / 충돌 마커 0 ✅

실 PDF E2E도 사용자가 직접 완주(HCI 문서: 업로드→정제→개념48→진단→선행삽입 학습까지 화면으로 확인).

---

## 5. 협의 필요 잔여 항목

1. **마이그레이션 스쿼시** — 양측 동시 진행 (단독 금지)
2. **ISSUE-019 데드락** — 진단 트랜잭션/LLM 경계 (2번 항목)
3. `concepts.key` — 지금 잠정 nullable (섭취 시점엔 없고 seed build가 채움). 합의 후 NOT NULL+UNIQUE 복원
4. `concept_mastery.answered_count` — 파생값 저장(코딩원칙② 위반 후보). 추후 attempts 집계로 대체 권장
5. 재진단 시 학습 mastery 리셋 정책 (업서트가 strength/resolved 초기화)
6. **이슈 번호 충돌** — 양측 016·017 각자 사용 중. 통합 시 번호 체계 정리
7. 개념 추출 품질(수식 문서): LLM 중복판정이 `행↔열`, `덧셈↔뺄셈`을 동일 병합 오판 / LaTeX 표기차(`x^2` vs `\(x^2\)`)로 문항 검수 불합격 — 판정 프롬프트 보강 여지
8. 대형 코스 진단 비용(개념 191 → 문항 배치 생성 느림) — 스코핑으로 완화했으나 상류 개념 수 자체도 검토

---

## 6. 실행법

```bash
cd ~/metalearn-mergecheck   # 또는 이 브랜치 체크아웃한 worktree
docker compose -f docker-compose.yml -f docker-compose.trial.yml up -d
# 프론트 http://localhost:55173/library  (dev 유저 자동, 로그인 불필요)
# 백엔드 http://localhost:58001/docs  (Swagger)
```
포트 5432/8000/5173은 다른 스택과 충돌 회피용으로 트라이얼은 55173/58001 사용 (docker-compose.trial.yml).
