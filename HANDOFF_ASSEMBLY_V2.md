# 병합 v2 인계 — parsing 신규 4기능을 full-assembly 위에 포팅

> 작성: 2026-07-07 · 브랜치: `trial/full-assembly-v2` (parsing 측)
> 베이스: `trial/full-assembly`(yoonhs) — UUID 코어 + parsing 옛 파이프라인 + 프론트 배선
> **이 브랜치 = 베이스 + parsing이 그 뒤 만든 4기능(배치고사·external_refs·비동기 ingest·슬러그)을 UUID로 포팅.**
> 바로 병합용 아님 — 리뷰 + 협의용. 마이그레이션 스쿼시는 양측 동시(단독 금지).

---

## 0. 30초 요약

`feat/parsing`에 `trial/full-assembly` 이후 4개 커밋(723ee32·ff158df·5dcd7f3·754dc8a)이
더 생겼다. 이걸 UUID 정본 코드 위에 **로직 무변경·타입/모델/import만 교체**해 포팅했고,
**빈 DB에서 업로드(비동기)→배치고사→씨앗→커리큘럼→학습생성→절 서빙 전 구간이 실제로 돈다.**
데드락(ISSUE-019) 재발 없음.

## 1. 포팅한 4기능

### ① 배치고사 (ISSUE-015) — 팀원 임시 스코핑(`_select_diag_targets`) 대체
- `diagnostic/placement.py`(신규) + `POST /api/diagnostic/placement/start`·`…/answer`, migration 0016(`diagnostic_sessions.kind/state`).
- linked = 천장에서 선수 사슬 depth 하강(선수 에지 1순위 + 이전 파트 대표 폴백, 첫 오답 1홉→이후 2홉, 이른 정답 확인 1문항), enumerative = 파트별 1문항. 상한 12.
- 스캔 파트 없음/단일 파트 문서면 섹션 대표(depth-0 book)를 문서순 샘플 단위로 폴백.
- 노이즈 파트 제외(ISSUE-018): 스캔 파트 `kind='special'`(refinement가 라벨) + 꼬마 파트 제외.
- **종료 시 `SeedService.finalize_placement(floor, ceiling)` 호출** → enrollment 확정.
- 팀원 스코핑 코드(`/diagnostic/start`)는 lab 호환용으로 남겨둠 — **삭제 여부는 협의**.
- ⚠️ **ISSUE-019 데드락 회피 준수**: enrollment/세션 락을 잡은 채 LLM await 안 함. 문항 생성(LLM) 직전마다 commit해 락 해제. (팀원 `record_attempt` 원칙과 동일)

### ② external_refs 수집 (ISSUE-017②) — 모델은 이미 있었고 "채우기"만 없었음
- `seed/refs.py`(신규). ko.wikipedia REST 검색(무키) → 실제 URL+snippet, 동음이의 기각, 미스는 LLM 폴백(`source_kind='llm'` 명시). 동시 3 + 429 대기 재시도.
- `seed.build_tree`에 연결 → ingest가 자동 수집. **E2E: ai_prereq 9개 → 9/9 수집(web 8·llm 1)**. 팀원 스택의 "external_refs 빈 채 → 절 조용히 빔" 갭 해소.

### ③ 비동기 ingest (ISSUE-010②)
- `documents/service.py`: `ingest` → `create_stub`(즉시 응답) + `run_pipeline`(BackgroundTasks). status 단계 노출: parsing→refining→chunking→extracting→building_seed→ready.
- 파이프라인 끝에 `seed.build_tree` 자동 실행(생성 직후 트리 존재). `POST /upload` 기본 background(응답 0.3초), `background=false` 동기 하위호환.
- 프론트 `uploadDocument.ts`는 내부 폴링으로 전환(호출부 계약 불변).

### ④ 슬러그 추출 동시 산출
- 추출 프롬프트 규칙 8 + `ConceptNode/SectionConcept.key`(optional). resolve에서 코스 내 유니크 가드(`UniqueConstraint(course_id,key)` 위반 방지). **E2E: 84/84 실슬러그, 폴백 0**.

## 2. 🔴 최우선 — 환경/정합 수정 2건 (병합 시 반영 필요)

1. **bcrypt/passlib 충돌 (`core/security.py`)** — passlib 1.7.4가 bcrypt 4.1+의 `__about__` 제거로 해싱 자체 실패(업로드 500). `hash_password`/`verify_password`를 **bcrypt 직접 호출 + 72바이트 절단**으로 교체. passlib 의존 제거. ⚠️ **auth 담당 확인 요망** — 팀원 verify DB에선 안 터졌으므로 bcrypt 버전 차이(uv가 5.0.0 해석).
2. **dev 유저 정합 (`auth/repository.py`)** — parsing 파이프라인은 `get_default_user()`(랜덤 UUID), 학습/프론트는 고정 `DEV_USER_ID(00000000-...01)`. 갈려서 **seed가 만든 enrollment를 커리큘럼이 못 찾음**("enrollment not found"). `get_default_user`가 고정 `DEV_USER_ID`를 쓰도록 통일. auth 붙으면 원복.

## 3. 검증 (2026-07-07, 실행함)

빈 DB(mlv2 스택, `docker-compose.trial.yml`)에서 전 구간:
- 업로드 비동기 응답 **0.3초**, 폴링으로 단계 전환 → ready
- 개념 84(book 75/ai_prereq 9), 슬러그 84/84, external_refs 9/9(web 8), 트리 챕터1·절18
- 배치고사: 전부 정답 → floor=ceiling(이미 앎) / 첫 오답 → 하강(매개변수→함수 정의) floor 확정. **데드락 0, Traceback 0(클린 런)**
- 커리큘럼 placement seeded 18(todo 12·locked 7·floor/ceiling=배치고사값) → 챕터 generate ready → 절 블록 서빙(이계도함수 5블록: concept/analogy/cloze/mcq/explainBack)
- 프론트(55173) 렌더 정상, 콘솔 에러 0

## 4. 협의 필요

1. 팀원 스코핑 진단(`_select_diag_targets`, `/diagnostic/start`) — 배치고사로 대체됐으니 삭제할지, config로 병존할지
2. seed 2단계(`/tree`·`/placement`)와 팀원 `/build`·커리큘럼 `/courses/{id}/placement`(학습 mastery 시드) — 이름/역할 경계 정리 ("placement"가 두 뜻)
3. bcrypt/dev-유저 수정 반영 여부 (2번 항목)
4. `concepts.key` NOT NULL 복원 시점 (이제 추출 동시 산출이라 대부분 채워짐)
5. 마이그레이션 스쿼시 (양측 동시)

## 5. 실행법

```bash
docker compose -p mlv2 -f docker-compose.yml -f docker-compose.trial.yml up -d
docker compose -p mlv2 exec backend uv run alembic upgrade head   # 0016까지
# 프론트 http://localhost:55173/library · API http://localhost:58001/docs
```
