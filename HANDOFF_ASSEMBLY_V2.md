# 병합 v2 인계 — parsing 신규 4기능을 full-assembly 위에 포팅

> 작성: 2026-07-07 · 갱신: 2026-07-08(실사용 테스트 후속, §5) · 브랜치: `trial/full-assembly-v2` (parsing 측)
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

1. 팀원 스코핑 진단(`_select_diag_targets`, `/diagnostic/start`) — 배치고사로 대체됐으니 삭제할지, config로 병존할지. **§5-1과 연결**: 스코핑 진단이 전 개념 mastery를 선생성해 커리큘럼 잠금 충돌을 유발 — 배치고사로 일원화하면 근원 해소.
2. seed 2단계(`/tree`·`/placement`)와 팀원 `/build`·커리큘럼 `/courses/{id}/placement`(학습 mastery 시드) — 이름/역할 경계 정리 ("placement"가 두 뜻)
3. bcrypt/dev-유저 수정 반영 여부 (§2 항목)
4. `concepts.key` NOT NULL 복원 시점 (이제 추출 동시 산출이라 대부분 채워짐)
5. **§5의 통합 수정 3건(ISSUE-013 잠금 해제·빈칸 LLM 채점·업로드 폴링) 리뷰** — 팀원 학습 코드(`learning/repository.py`·`grading.py`)를 건드렸으므로 담당 확인 요망
6. 마이그레이션 스쿼시 (양측 동시)

## 5. 실사용 테스트 후속 발견 (2026-07-08) — 통합 버그 3 + UX 1

포팅 후 프론트(55173)로 실제 정처기 PDF를 업로드→진단→커리큘럼→학습까지
사람이 눌러보며 발견. **§3 클린 E2E가 못 잡은 것들** — 전부 진단/씨앗(parsing)과
학습(팀원)이 만나는 경계라 병합 화해 성격. 이 브랜치에 수정+커밋 완료.

1. **[🔴 통합] 진단 후 커리큘럼 콘텐츠 전부 잠김 (ISSUE-013)** — 커밋 `42de0bc`
   - 증상: 진단 10문항 완료 후 커리큘럼 들어가면 내용이 안 뜸.
   - 원인: 진단(BKT)이 `concept_mastery` 전 행을 `status='locked'`(기본값)로 미리
     생성 → 커리큘럼 `initialize_placement`의 `seed_mastery_if_absent`가 "이미
     있음"으로 전부 스킵 → status를 못 깔아 전 절 잠김. **팀원이 `initialize_placement`
     docstring에 예고한 바로 그 ISSUE-013 지점** (진단/커리큘럼을 각자 검증해 미발견).
   - 수정(`learning/repository.py`): 기본 locked 행은 placement 판정으로 status 갱신,
     실제 학습 진행된 행(todo/learning/mastered)은 보존. 프론트는 이미 진단 후
     `seed build → placement`를 부르므로 이 수정만으로 자동 해소.
   - 실측: 정처기 982행 전부 locked → mastered 3/todo 28/locked 951, 콘텐츠 렌더 확인.
   - ⚠️ **참고**: 내 배치고사(placement.py)는 응답 개념만 mastery를 만들어 이 충돌이
     없다. 팀원 스코핑 진단(전 개념 선생성)이 이 문제의 근원 — §4-1 협의와 연결.

2. **[🟡 통합] 빈칸 서답형 오채점 (ISSUE-016③ 계보)** — 커밋 `42de0bc`
   - 증상: 옳은 답을 넣어도 "틀린 빈칸" 처리.
   - 원인: 자유서술 빈칸(수식·개념)이 정규화 완전일치만 인정 → 표기 차이로 오답
     (예: `f''(a)=0` vs `f''(a) = 0`). 진단엔 LLM 심판 폴백이 있으나 학습 채점엔 없었음.
   - 수정(`learning/grading.py`): 정확일치 실패 시에만 LLM 의미 채점(비용 절약).
     실측: 표기변형 인정, `0`·`f''(a)>0` 등 진짜 오답은 거름.

3. **[🟡 회귀] 비동기 ingest가 프론트 동기 가정을 깸** — 커밋 `7260721`
   - 증상: 업로드 직후 진단 호출이 400(개념 추출 전).
   - 원인: 비동기 ingest가 즉시 `processing` 반환 → 프론트가 완료로 오인하고 진단 진입.
   - 수정(`uploadDocument.ts`): course status를 ready까지 폴링 후 반환(계약 불변).
     모든 업로드 경로가 이 함수 하나를 거쳐 일괄 해소.

4. **[🟢 UX] 다음 강의 '생성 중' 대기 제거** — 커밋 `765b23a`
   - 요청: 절 끝나고 다음 강의로 넘어갈 때 '생성 중' 없이 바로 뜨게.
   - 수정(`LearningPage.tsx`): 현재 챕터 진입 시 다음 챕터가 pending이면 백그라운드
     생성 미리 트리거(멱등, 챕터당 1회). JIT 생성 ~1~2분이라 챕터 단위로 앞서 생성.
   - 한계: 챕터가 짧고 아주 빨리 풀면 생성이 못 끝날 수 있음 → 필요 시 2챕터 앞서로 확대.

5. **[🟡 품질/UX] 잘못된 문항 + 오답 피드백 부재 (ISSUE-016)** — 커밋 `a309a3f`
   - 증상: inverse 문항 "AI에 윤리적 책임 전가를 주장하는 **사람은 누구**인가?"
     정답 "**도덕적 주체**"(개념) — 문두(누구/사람)와 정답(개념)이 불일치. 또
     틀려도 "왜 틀렸는지" 안 알려줌.
   - 원인 A: 검증 패스가 mcq 정답 정합·자유서술 의미일치만 봐서, 문두↔정답
     **유형** 불일치(누구인데 개념 답)를 못 걸렀다.
   - 원인 B: 채점기가 자유서술 심판의 `rationale`(왜 틀린지)을 계산하고도 버림.
   - 수정(`diagnostic/service.py`·`schemas.py` + 프론트 2곳):
     A. `_verify_prompt`에 문두 의문사↔정답 유형 일치를 **최우선 하드 게이트**로
        추가(누구→사람, 무엇→개념, 몇→수…). 불일치면 재생성. 실측: 누구→개념
        일관 적발, 정상 문항 오탐 0(2회).
     B. `_grade_with_feedback` 신설로 심판 rationale 표면화(추가 비용 0, mcq는
        정답 해설). `_grade`는 bool 하위호환 유지(배치고사 등 무영향).
        `AnswerResult.feedback` + 진단 화면(`DiagnosticPanel`/`DiagnosisPage`)에
        "왜 틀렸나:" 표시.
   - ⚠️ 검증 강화는 **새로 생성되는** 문항부터 적용 — DB의 기존 문항은 재진단/재생성 시 반영.

## 6. 실행법

```bash
docker compose -p mlv2 -f docker-compose.yml -f docker-compose.trial.yml up -d
docker compose -p mlv2 exec backend uv run alembic upgrade head   # 0016까지
# 프론트 http://localhost:55173/library · API http://localhost:58001/docs
```
