# MetaLearn 작업 일지 (WORK_LOG)

> **Cursor ↔ Claude CLI 공용 일지.** 세션마다 **맨 위에** 새 항목을 append한다.  
> 고정 컨텍스트(제품 철학·아키텍처)는 [`CLAUDE_CONTEXT.md`](./CLAUDE_CONTEXT.md)만 수정한다.

---

## 에이전트 규칙 (Cursor / Claude CLI 공통)

작업 **시작 전** 반드시 읽기:

1. `docs/CLAUDE_CONTEXT.md` — 제품·아키텍처·코딩 원칙
2. `docs/WORK_LOG.md` (이 파일) — **최신 항목 + 열린 이슈 + 다음 액션**

작업 **종료 시** 반드시 기록:

1. 이 파일 **맨 위(구분선 아래)** 에 새 세션 블록 추가 (아래 템플릿 사용)
2. 버그/이슈 상태 변경 시 **열린 이슈** 섹션 갱신
3. 구현 상태가 바뀌면 `CLAUDE_CONTEXT.md` §3 표·§7 표만 짧게 갱신 (일지 본문은 이 파일에만)

### 세션 로그 템플릿

```markdown
## YYYY-MM-DD — [에이전트: Cursor|Claude CLI] — [한 줄 요약]

### 사용자 요청
-

### 추론 / 결정
- 왜 이렇게 했는지

### 한 일
-

### 변경 파일
-

### 결과
-

### 검증
- 실행한 명령·테스트·결과

### 열린 이슈 (이번에 생기거나 남은 것)
- [ ] ...

### 다음 액션
1.
```

---

## 열린 이슈 (스냅샷)

| ID | 우선순위 | 상태 | 내용 |
|----|----------|------|------|
| ISSUE-001 | **P0** | ~~closed~~ | BKT `_params()`: `strength_init` → `p_init` (`diagnostic/service.py:117-118`) — 답안 제출 시 TypeError. **2026-07-02 Claude CLI가 수정, 같은 세션에서 실제 Docker+DB로 E2E 확인 완료(진단 세션 10/10, 크래시 없음).** |
| ISSUE-002 | P1 | open | `materials→documents` 등 대규모 변경 **미커밋** (브랜치 `feat/parsing`) |
| ISSUE-003 | P1 | ~~closed~~ | migration `0009` 미적용 가능성 우려했으나, **2026-07-02 확인: `alembic current`가 이미 `0009 (head)`** — 실제로는 문제 없었음 |
| ISSUE-004 | P2 | open | `seed` 도메인 스텁 — 씨앗 formalize 미구현 |
| ISSUE-005 | P2 | open | 학습 중 확인 루프 (서버 채점·오답분석·재설명·재생성) 미구현 |
| ISSUE-006 | P3 | open | README `materials` 등 outdated |
| ISSUE-007 | P1 | ~~closed~~ | `learning/service.py` 커리큘럼 모드 분기가 X 자신의 strength만 보고 결정되던 문제. **2026-07-02 Claude CLI가 수정 + 실제 API로 두 분기 모두 재검증 완료.** |

### 다음 액션 (팀 합의 대기 없음 — 우선순위 제안)

1. **ISSUE-002** 변경사항 커밋 (사용자 요청 시)
2. 학습 중 확인 루프 설계·구현 (§9-1 in CLAUDE_CONTEXT)
3. seed 서비스 formalize (§9-2)

---

## 2026-07-02 — Claude CLI — ISSUE-007 수정 (커리큘럼 모드가 선수 강도 무시하던 문제)

### 사용자 요청
- "ISSUE-007 지금 고쳐줘"

### 추론 / 결정
- 사용자 철학 원문 기준으로 분기 규칙을 다시 세움: X 자신이 강하면(≥0.5) → focused(기존과 동일). X가 약해도, 직접 선수 중 "약한 것"이 하나도 없으면(선수가 전부 이미 앎, 혹은 애초에 선수가 없음) → **focused**(신규). X도 약하고 약한 선수도 있으면 → bridge(기존과 동일, 단 해당 약한 선수만 포함).
- 구현 방법 선택: `high` 판정에 `or not weak_prereqs`를 추가하는 방식 채택. 대안으로 "모드는 그대로 X 강도로만 정하고 bridge일 때 약한 선수가 없으면 그 섹션만 생략"하는 방식도 있었지만, 그러면 응답의 `mode` 필드가 "bridge"인데 실제로는 100% 본문인 상태가 되어 프론트/로그에서 오해를 유발할 수 있음 → mode 필드 자체를 focused로 바꾸는 게 더 정직하다고 판단.
- `_weak_prerequisites()`의 `return weak or direct` 폴백 제거 — 이 폴백이 있으면 "weak 리스트가 비었을 때 전체 선수를 돌려주는" 이상한 의미가 되어 위 mode 판정과도 모순됨. 제거 후 `weak`(빈 리스트 가능)를 그대로 반환하도록 단순화.
- 세션 없는 경우(`session_id is None`)의 기존 보수적 fallback(직접 선수 전체를 weak로 간주)은 그대로 유지 — 이건 "모르니까 안전하게 bridge" 케이스라 이번 이슈와 무관.

### 한 일
- `backend/app/features/learning/service.py`
  - `generate_curriculum()`: `weak_prereqs`를 먼저 계산하고 `high = score >= LEARNING_HIGH_THRESHOLD or not weak_prereqs`로 변경, `used_prereqs`도 `weak_prereqs` 재사용
  - `_weak_prerequisites()`: `return weak or direct` → `return weak` (직접 리스트 컴프리헨션을 그대로 반환)
- `ast.parse`로 문법 확인
- 이미 떠 있는 backend 컨테이너(`--reload`)로 실제 API 재검증 (아래 검증 항목)

### 변경 파일
- `backend/app/features/learning/service.py`
- `docs/WORK_LOG.md` (이 항목, ISSUE-007 closed, 다음 액션 갱신)
- `docs/CLAUDE_CONTEXT.md` (§3 ⑤, §7 bridge/focused 행 갱신)

### 결과
- concept 1(X strength 0.043, 직접 선수 concept 2가 실제로 0.885까지 앎) → **focused**로 정정됨 (수정 전엔 bridge였음)
- 같은 concept 1을 대상으로, 선수(concept 2) strength를 일시적으로 0.2로 낮춰서(DB 직접 UPDATE, 검증 후 원복) 재확인 → **bridge**로 정상 전환, `prerequisite_names: ["다중 모달 융합"]`로 실제 약한 선수만 정확히 표기됨
- concept 3(X strength 0.9507, 애초에 강함) → 기존과 동일하게 focused, 회귀 없음 확인

### 검증
- `POST /api/learning/curriculum {concept_id:1, session_id:5, force_regenerate:true}` (수정 후, 선수 strength=0.885 그대로) → `mode: focused, prerequisite_names: []`
- DB에서 `concept_mastery.strength`(concept_id=2)를 0.2로 임시 변경 → 동일 요청 재실행 → `mode: bridge, prerequisite_names: ["다중 모달 융합"], block count: 7`
- 검증 직후 concept 2 strength를 실제 진단 결과값(0.8852459016393444)으로 원복 — 세션 5의 씨앗 데이터가 실제 답안 제출 결과와 다시 일치하도록 정리함
- `POST /api/learning/curriculum {concept_id:3, session_id:5}` (회귀 확인) → 여전히 `mode: focused`

### 열린 이슈
- [x] ISSUE-007 — 수정 + 두 분기(focused/bridge) 모두 실제 API로 재검증 완료. 완전 종료.

### 다음 액션
1. ISSUE-002 커밋은 여전히 사용자 확인 대기
2. 학습 중 확인 루프(ISSUE-005), seed formalize(ISSUE-004) 순으로 다음 후보

---

## 2026-07-02 — Claude CLI — 핵심 제품 루프 실제 E2E 검증 (Docker+DB, 코드 변경 없음)

### 사용자 요청
- "변경 사항 진행 하지말고 내 서비스 어떤지 한번 검증 해줘" — 사용자가 진단(수준 파악) 철학을 직접 다시 설명: A 문제 틀림→A 모름, 선수지식도 모르면 선수 뼈대부터 쌓고 A 설명(bridge), A는 약해도 선수는 알면 본문(A)만 집중(focused) — 개념마다 다르게 판단, 전원에게 선수를 깔지 않음. 이 씨앗으로 커리큘럼을 만든다는 전체 흐름이 실제로 동작하는지 확인 요청.

### 추론 / 결정
- 이미 떠 있던 Docker 컨테이너(`docker ps`로 확인, 47시간 전 기동)를 재사용하기로 결정 — `docker-compose.yml`에 `./backend:/app` 바인드 마운트 + `--reload`가 걸려 있어 방금 고친 ISSUE-001 수정사항이 이미 반영돼 있음을 먼저 확인 후 진행.
- 새 PDF를 업로드하는 대신 이미 존재하는 course_id=2("음향 논문", status=ready, 10개 개념)를 재사용 — 실제 Solar 파싱으로 만들어진 진짜 데이터라 (1)번 검증(업로드→파싱→그래프)을 새로 돌릴 필요 없이 이미 증명된 상태였음. 불필요한 Solar API 비용도 피함.
- 진단 세션은 실제로 새로 시작해서(session_id=5) 답을 의도적으로 섞어 제출 — 일부러 틀리고 일부러 맞혀서 게이티드 로직의 두 분기(정답→서브트리 확정, 오답→직접 선수 1단계 unlock)를 모두 관찰.
- 각 정답/오답 제출 후 API 응답만 보지 않고 `docker compose exec db psql`로 `concept_mastery`/`diagnostic_questions` 테이블을 직접 조회 — API 응답 JSON만으로는 "locked" 플래그나 "언제 질문이 생성됐는지"가 안 보여서, 게이팅이 진짜 DB 레벨에서 의도대로 동작하는지 확인하려면 직접 쿼리가 필요하다고 판단.
- 커리큘럼 생성까지 실제로 호출해서 bridge/focused 분기를 확인하던 중, concept 1의 선수(concept 2)가 이미 강하게 알려진 상태(strength 0.885)인데도 bridge 모드가 나오고 "약한 선수개념"이라고 표기되는 걸 발견 → 우연이 아닌지 확인하려고 `learning/service.py` 소스를 직접 읽어서 원인을 특정(`_weak_prerequisites()`의 `weak or direct` 폴백, 그리고애초에 모드 자체가 X의 strength만 보고 결정되는 구조).

### 한 일
1. `docker ps` / `docker compose exec backend uv run alembic current` — 컨테이너 상태 및 migration 버전(0009, head) 확인 → ISSUE-003 우려 해소
2. `GET /api/documents/courses`, `/api/documents/courses/2` — 기존 실제 업로드 데이터로 개념+선수지식 그래프 확인 (10개 개념, 5개 메인+5개 직접 선수, depth_level 0/1)
3. `POST /api/diagnostic/start` (course_id=2) → session_id=5, 메인 5개 개념만 배치 출제 확인
4. 답 6개를 실제로 제출(`POST .../answer`): 메인 개념 중 2개(concept 1, 7)는 의도적 오답, 나머지 3개(concept 3, 5, 9)는 정답, 오답으로 unlock된 선수(concept 2, 8)는 정답 제출 → 세션 완료(done=true, 10/10 resolved)까지 전 구간 무크래시 확인
5. 매 단계마다 `concept_mastery`/`diagnostic_questions` 테이블 직접 쿼리로 `locked`/`resolved`/`answered_count`와 실제 질문 생성 시점 대조
6. `POST /api/learning/curriculum`을 concept_id=1(약함, 0.043)과 concept_id=3(강함, 0.9507) 둘 다 호출해 bridge/focused 응답 비교
7. `backend/app/features/learning/service.py` 전체 읽고 모드 분기·`_weak_prerequisites()` 로직 재확인 (코드 수정은 안 함)

### 변경 파일
- 없음 (코드 변경 없음 — 사용자가 명시적으로 요청)
- 문서: `docs/CLAUDE_CONTEXT.md` §3·§7 상태 갱신, `docs/WORK_LOG.md` 이 항목 + 열린 이슈 표(ISSUE-001 E2E 확인 완료로 격상, ISSUE-003 closed, ISSUE-007 신규 등록)
- 부수효과(DB 데이터, 코드 아님): dev DB에 진단 세션 `session_id=5`, 커리큘럼 레코드 2건(concept 1, concept 3)이 테스트 결과물로 생성됨 — 실제 코드/스키마 변경은 아니지만 참고용으로 남김. 필요하면 정리해도 무방.

### 결과 — 사용자가 설명한 철학 대비 실제 동작
| 사용자가 설명한 로직 | 실제 검증 결과 |
|---|---|
| PDF→파싱→개념+선수지식 그래프 | ✅ 확인 (기존 실사용 데이터, 10개 개념, prerequisite 엣지 정상) |
| A 틀리면 A 모름, 선수도 모르면 선수부터 확인 | ✅ 확인 — 오답 시 직접 선수가 `locked:false`로 풀리고 그 즉시 새 문제가 지연 생성됨(concept 1 오답→concept 2 문제 생성, concept 7 오답→concept 8 문제 생성) |
| A는 맞고 선수도 안다고 볼 수 있으면 생략 | ✅ 확인 — 정답 시 직접 선수가 `resolved:true, strength=0.9, answered_count=0`(질문 자체를 생성 안 함)으로 자동 확정, `locked:true` 유지(출제 화면엔 안 나옴) |
| 씨앗(개념별 프로필) 완성 | ✅ 확인 — 세션 종료 시 10개 개념 전부 `resolved:true`, 개념마다 실제 채점 결과를 반영한 서로 다른 strength |
| **A는 약해도 선수는 알면 → 본문(A)만 집중** | ⚠️ **불일치 발견 (ISSUE-007)** — concept 1은 strength 0.043(약함)인데 그 직접 선수(concept 2)는 사용자가 방금 정답으로 맞혀 strength 0.885(충분히 앎)까지 올라간 상태. 사용자 철학대로면 이건 focused(본문만)여야 하는데, 실제로는 **여전히 bridge 모드**로 응답하고 "선수개념: 다중 모달 융합" 챕터를 그대로 포함시킴. 원인: `generate_curriculum()`이 모드를 결정할 때 X 자신의 strength만 보고(`score >= 0.5`), 선수의 상태는 전혀 고려하지 않음. 게다가 `_weak_prerequisites()`가 "약한 선수가 하나도 없으면 그냥 전체 직접 선수를 돌려준다"는 폴백(`weak or direct`)을 갖고 있어서, 강한 선수도 "아직 약한 선수개념"이라고 LLM 프롬프트에 그대로 들어감. |
| bridge = 선수+본문, focused = 본문만 (모드 자체의 콘텐츠 구성) | ✅ 확인 — bridge 응답은 "선수개념: …" 챕터 + "메인 개념: …" 챕터 혼합(6블록), focused 응답은 메인 개념 챕터만(4블록), `prerequisite_names`도 focused에선 빈 배열 |
| 답안 채점 API가 안 죽는지(ISSUE-001) | ✅ 확인 — 실제 답안 6건 전부 정상 채점, 진단 세션 완주 |

### 검증
- `docker compose exec backend uv run alembic current` → `0009 (head)`
- `curl .../api/documents/courses/2` → 개념 10개, prerequisite_ids 정상
- `curl -X POST .../api/diagnostic/start` → session 5 생성, 메인 5문항 배치 생성 확인
- `curl -X POST .../questions/{id}/answer` × 6회 → 전부 200 응답, 크래시 없음, `is_correct`/`strength` 정상 갱신
- `docker compose exec db psql ... concept_mastery` × 2회(중간/최종) → `locked`/`resolved` 전이가 게이팅 로직과 정확히 일치
- `docker compose exec db psql ... diagnostic_questions` → 지연 생성된 선수 문항(concept 2, 8)이 오답 시점에만 생성됐음을 타임라인으로 확인
- `curl -X POST .../api/learning/curriculum` (concept 1, concept 3) → bridge/focused 블록 구성 비교, `learning/service.py` 소스 재확인으로 원인 특정

### 열린 이슈 (이번에 생기거나 남은 것)
- [x] ISSUE-001 — 이번 세션에서 실제 API E2E까지 확인 완료 (완전 종료)
- [x] ISSUE-003 — migration 걱정 해소 (이미 0009 head 적용됨, closed)
- [ ] **ISSUE-007 (신규, P1)** — 커리큘럼 모드 분기가 선수지식 강도를 반영 안 함 + `_weak_prerequisites()` 폴백이 강한 선수를 "약함"으로 오표기. 사용자가 명시한 제품 철학과 직접 충돌하는 부분이라 우선순위 높게 등록.

### 다음 액션
1. 사용자 확인 필요: ISSUE-007을 어떻게 고칠지 방향 결정 필요 — (a) 모드 결정 자체에 선수 강도를 반영할지(예: X 약함+선수도 약함일 때만 bridge, 선수가 이미 강하면 X가 약해도 focused), (b) 아니면 모드는 X 강도로만 결정하되 `_weak_prerequisites()`의 fallback만 없애서 "약한 선수 없으면 브릿지 섹션 자체를 생략"할지 — 사용자의 원래 설명("A는 약하지만 선수는 안다 → 본문만")은 (a)에 더 가까움
2. ISSUE-002(커밋), ISSUE-004(seed), ISSUE-005(학습 확인 루프) 등은 그대로 대기

---

## 2026-07-02 — Claude CLI — ISSUE-001 (BKT 채점 크래시) 수정

### 사용자 요청
- "ISSUE-001부터 수정해줘"

### 추론 / 결정
- 이전 세션에서 이미 원인을 정확히 특정해둔 상태(`service.py:117-118`의 `bkt.BKTParams(strength_init=...)` 호출 vs `bkt.py:18`의 dataclass 필드 `p_init`)라 원인 재조사 없이 바로 수정.
- 수정 방향은 `strength_init` 인자명을 `p_init`으로 맞추는 것(반대로 `bkt.py`의 dataclass 필드를 `strength_init`으로 바꾸는 방향은 채택 안 함) — `bkt.py`는 "순수 로직, DB 비의존"이라고 파일 docstring에 명시돼 있고 `p_init/p_transit/p_slip/p_guess`는 BKT 표준 표기(§ 파일 상단 주석)라서 DB 컬럼명(`strength`) rename과 별개로 유지하는 게 맞다고 판단. 즉 이번 리네임 작업(`p_known`→`strength`)이 실수로 BKT 내부 파라미터명까지 건드린 것이었고, 그걸 원복하는 게 올바른 수정.
- Docker/DB 없이 코드 레벨 검증만 수행 (풀 E2E는 안 돌림) — 그래서 상태 표기를 "✅ 구현 완료"가 아니라 "✅ 수정 완료, E2E 미검증"으로 남김.

### 한 일
- `backend/app/features/diagnostic/service.py:117-118` — `bkt.BKTParams(strength_init=...)` → `bkt.BKTParams(p_init=...)`로 수정 (들여쓰기 오류도 같이 정리)
- `ast.parse`로 두 파일 문법 검사
- `bkt.py`를 직접 import해서 `BKTParams(p_init=...)` 생성 + `update()` 호출까지 정상 동작 확인
- 비교용으로 옛 방식(`strength_init=...`)이 실제로 `TypeError`를 던지는지 재현해 버그가 진짜였음을 재확인
- `CLAUDE_CONTEXT.md` §3·§7 상태 표, `WORK_LOG.md` 열린 이슈 표(ISSUE-001 → closed) 갱신

### 변경 파일
- `backend/app/features/diagnostic/service.py` (버그 수정)
- `docs/CLAUDE_CONTEXT.md` (§3, §7 상태 갱신)
- `docs/WORK_LOG.md` (이 항목, ISSUE-001 상태 갱신)

### 결과
- `BKTParams` 생성 및 `bkt.update()` 호출이 코드 레벨에서 정상 동작 확인됨
- `backend/app/features/diagnostic/repository.py:100`의 `create_masteries(strength_init=...)`는 별개 함수 파라미터라 원래부터 버그 아니었음 — 그대로 유지

### 검증
- `python -c "ast.parse(...)"` — 문법 OK
- `python -c "from app.features.diagnostic import bkt; bkt.BKTParams(p_init=0.3, ...); bkt.update(...)"` — 정상 동작 (`update() OK: 0.646...`)
- 동일 스크립트에서 `BKTParams(strength_init=...)` 호출 시 `TypeError: unexpected keyword argument 'strength_init'` 재현 → 수정 전 상태가 실제로 깨져 있었음을 재확인
- **미검증**: FastAPI/DB 붙여서 실제 `/api/diagnostic/answer` 엔드포인트 호출까지는 안 해봄 (`fastapi` 모듈이 이 세션의 파이썬 환경에 없어서 서비스 레이어 전체 임포트 불가 — `uv`/Docker 환경에서 별도 확인 필요)

### 열린 이슈
- [x] ISSUE-001 — 코드 수정 완료. E2E 미검증이므로 완전 종료는 아님 (WORK_LOG 표에 "closed (E2E 미검증)"로 표기)

### 다음 액션
1. Docker 기동 후 실제 진단 플로우(세션 시작 → 답안 제출)로 ISSUE-001 E2E 확인
2. 사용자 확인 후 ISSUE-002(커밋) 등 다음 이슈 진행

---

## 2026-07-02 — Claude CLI — 세션 인수인계 로그 (Cursor 전환 대비 상세 기록)

### 사용자 요청
- "동기화 후 작업 시작" (처음엔 git 동기화로 오해 → 사용자가 "커서가 만든 md 파일 내용을 너도 이해하라는 뜻"이라고 정정)
- 이후 "내가 너랑 작업한 내용도 커서가 알아야 하니 너도 커서랑 동기화해야 해" → 문서에 되먹임 요청
- "피드백이나 선택/작업 부여 물어볼 때도 한국어로" → 응답 언어 확정 (AskUserQuestion 포함)
- 지금: "커서로 넘어가도 작업 내용 안 달라지게 로그·추론 상세히 작성" (이번 항목)

### 추론 / 결정
- **git 동기화를 먼저 확인한 이유**: "동기화"가 git pull을 뜻하는지 문맥상 불확실 → `git fetch` + `git log origin/feat/parsing`로 원격에 새 커밋 없음을 먼저 확정한 뒤 나머지 작업 진행. (결과: 새 커밋 없음, 로컬이 원격보다 앞서 있는 게 아니라 **커밋 안 된 변경**이 쌓여 있는 상태였음)
- **문서 내용을 코드로 직접 재검증한 이유**: `CLAUDE_CONTEXT.md`는 Cursor가 작성한 문서라 실제 코드(특히 rename 작업 중인 uncommitted 상태)와 어긋났을 가능성이 있다고 판단 → Explore 서브에이전트로 7개 핵심 주장(게이티드 BKT, bridge/focused 분기, ingestion, config 임계값, seed/auth 스텁 여부, 학습 확인 루프 미구현)을 코드에서 직접 확인. 문서를 그대로 믿지 않고 검증하는 게 `CLAUDE_CONTEXT.md` §12 "README만 믿지 말고 코드 확인"과 같은 원칙이라 판단.
- **ISSUE-001 (BKT 버그)을 바로 고치지 않은 이유**: 사용자가 아직 "뭐부터 할지" 명시 지시를 안 한 상태 → 최소 diff·무단 변경 금지 원칙상 발견만 보고하고 우선순위 선택은 사용자에게 맡김. (AskUserQuestion으로 두 번 물었으나 응답 없이 다른 지시로 전환됨 — 아직 미확정)
- **문서에 로그를 직접 쓰기로 한 이유**: Cursor는 Claude의 대화 메모리를 못 읽으므로, 세션에서 발견한 사실(버그, 검증 결과)은 반드시 공유 파일(WORK_LOG.md)에 남겨야 인수인계가 됨. Claude 자체 메모리(`~/.claude/.../memory/`)에는 "동기화 절차가 이렇게 바뀌었다"는 워크플로우 규칙만 남기고, 프로젝트 사실 정보는 전부 이 파일에 기록.

### 한 일
1. `git fetch origin` + `git log` 비교 → `feat/parsing`은 `origin/feat/parsing`과 완전히 동기화, 새로 pull할 팀원 커밋 없음을 확인
2. `git status` / `git diff --stat` → uncommitted 변경 목록 전수 파악 (materials 삭제 5파일, documents 신규, diagnostic/learning 수정 9파일, auth 신규 2파일, migration 0009 신규)
3. Explore 서브에이전트로 `CLAUDE_CONTEXT.md` §1~12 주장 7개 항목을 코드와 교차검증 → 전부 일치, 단 하나 불일치 발견
4. **ISSUE-001 직접 재현 확인**: `backend/app/features/diagnostic/service.py:117-118`의 `_params()`가 `bkt.BKTParams(strength_init=settings.BKT_P_INIT, ...)`로 호출하지만, `backend/app/features/diagnostic/bkt.py:18`의 `BKTParams` dataclass 필드는 `p_init`. `_params()`는 답안 채점 경로(`service.py:199`)에서 호출되므로 답안 제출 시 `TypeError` 크래시 확정. (참고로 `repository.py:100`의 `create_masteries(strength_init=...)`는 별개 함수라 버그 아님 — `_params()` 호출부만 문제)
5. 최초엔 `CLAUDE_CONTEXT.md` §13에 로그 기록 → 이후 Cursor가 세션 중 파일을 `CLAUDE_CONTEXT.md`(고정 맥락) / `WORK_LOG.md`(일지, 이 파일)로 분리 재구조화 → 이 항목부터는 새 규칙(WORK_LOG 맨 위 append)을 따름

### 변경 파일
- 코드 변경 **없음** (이번 세션은 읽기·검증만 수행, 실제 수정은 하지 않음)
- 문서: `docs/CLAUDE_CONTEXT.md` §13에 로그 추가했었으나, 이후 Cursor의 문서 분리 작업으로 해당 내용은 제거·`WORK_LOG.md`로 대체됨 (아래 "2026-07-02 — Cursor — 문서 분리" 항목 참고)

### 결과
- `ISSUE-001`은 **여전히 미수정** 상태로 남아 있음 (재현만 확인, 코드 수정 안 함)
- uncommitted 변경사항(`ISSUE-002`)도 그대로 미커밋 상태
- 사용자와 나눈 대화에서 확정된 협업 규칙: (1) 한국어로만 대화·질문, (2) 세션 내 발견 사항은 이 파일에 기록해서 Cursor와 공유, (3) 사용자가 명시적으로 지시하기 전엔 버그 수정·커밋 등 실질적 코드 변경을 먼저 하지 않음

### 검증
- `git fetch origin` → 새 커밋 없음 확인
- `git status --porcelain backend/app/features/auth/` + `git ls-files` → auth의 `__init__.py`/`router.py`는 기존 커밋(b3bc4ed) 소속, `models.py`/`repository.py`만 신규임을 라인 단위로 확인
- `backend/app/features/diagnostic/service.py:111-122`, `bkt.py:16-21`, `repository.py:100,108` 직접 Read로 대조 → ISSUE-001 필드명 불일치 재확인

### 열린 이슈
- 변동 없음. `ISSUE-001~006` 스냅샷(상단 "열린 이슈" 표) 그대로 유효. 이번 세션에서 새로 발견한 이슈는 없음 (ISSUE-001은 이전에 이미 이 세션에서 최초 발견 후 등록됨).

### 다음 액션
1. **사용자 결정 대기**: ISSUE-001 수정 / uncommitted 커밋(ISSUE-002) / migration 0009 적용 확인(ISSUE-003) / 학습 확인 루프(ISSUE-005) / seed formalize(ISSUE-004) 중 우선순위 미확정 — 다음 세션(Cursor든 Claude CLI든) 시작 시 사용자에게 재확인 필요
2. (제안) 리스크·되돌리기 난이도가 가장 낮고 P0인 ISSUE-001부터 처리하는 게 합리적이라고 판단되나, 사용자 확답 전엔 착수하지 않음

---

## 2026-07-02 — Cursor — 문서 분리 (CLAUDE_CONTEXT / WORK_LOG)

### 사용자 요청
- 컨텍스트와 일지 파일 분리
- Cursor에서 한 모든 작업·추론·결과를 Claude CLI가 파일만 읽고 이어갈 수 있게 정리

### 추론 / 결정
- `CLAUDE_CONTEXT.md`: 변하지 않는 제품·기술 맥락 + 구현 상태 스냅샷
- `WORK_LOG.md`: 시간순 일지 + 열린 이슈 + 다음 액션 (append-only)
- 과거 Cursor 대화 내용을 역사 섹션으로 백필

### 한 일
- `docs/WORK_LOG.md` 생성 (이 파일)
- `docs/CLAUDE_CONTEXT.md`에서 §13 세션 로그 제거, 문서 구조·에이전트 규칙 추가

### 결과
- Claude CLI 시작 시 두 파일만 읽으면 작업 재개 가능한 구조

---

## 2026-07-02 — Cursor — Claude CLI 로그 품질 검토

### 사용자 요청
- Claude가 `CLAUDE_CONTEXT.md` §13에 남긴 로그가 잘 되고 있는지 검토

### 추론 / 결정
- 로그 내용은 **사실과 일치** (git 상태, BKT 버그) — 품질 양호
- 다만 §13에 일지+컨텍스트 혼재 → 파일 분리 권장 (이번에 실행)

### 검증
- `git status`: uncommitted materials→documents, 0009 migration 등 확인
- `service.py:117` + `bkt.py:18`: `strength_init` vs `p_init` 불일치 확인 → **ISSUE-001**

---

## 2026-07-02 — Claude CLI — 컨텍스트 교차검증 + 버그 발견

### 사용자 요청
- (암묵) `CLAUDE_CONTEXT.md` 읽고 프로젝트 동기화

### 한 일
- git 원격·로컬 uncommitted 변경 파악
- 문서 §1~12 vs 코드 교차검증 (게이티드 BKT, bridge/focused, ingestion 등 일치)
- BKT 채점 크래시 버그 발견 → §13에 기록 (후에 WORK_LOG로 이관)

### 열린 이슈
- ISSUE-001 등록

---

## 2026-06-30 전후 — Cursor — 제품 이해·흐름·팀 스키마 논의 (백필)

### 배경
팀원 full SaaS 스키마(~25 테이블) vs 현재 MetaLearn 구현(8→확장) 비교·정렬 작업이 진행됨.

### 사용자가 확정한 제품 철학 (핵심)
1. 개인 교재 PDF → LLM 파싱 → 개념+선수지식 그래프
2. 문제로 수준 파악: A 틀림 → A 모름; **선수도 모르면** A만 가르쳐도 소용없음 → **선수 뼈대 후 A**
3. A 약하지만 선수는 앎 → **교재 본문만**
4. 전원에게 선수 깔지 않음 — **개념마다** 다름
5. 진단 결과 = **씨앗** (사용자×교재 프로필)
6. 씨앗으로 **개념별** JIT 커리큘럼 (`bridge` = 선수+본문, `focused` = 본문만)
7. 학습 중: 까먹음/이해 확인 → 틀리면 **왜 틀렸는지 분석** → 재설명/커리큘럼 재생성 (목표, 미구현)

### 논의·결론 요약

| 주제 | 결론 |
|------|------|
| 팀원 스키마 중 MVP에 과한 것 | 결제, 알림, 4단 CMS, SM-2 등 |
| 정식 출시 기준에서도 MetaLearn과 안 맞는 것 | `serve_variant`, `external_refs`/verified, related/application 엣지, ceiling/floor 진단, push_tokens, JIT 제품에 4단 CMS |
| 동일 엔티티 다른 이름 | materials≈documents, p_known≈strength, concept_prerequisites≈concept_edges 등 |
| rename + 부모 테이블 추가 | 코드 반영 완료, **미커밋** |
| 벡터화 범위 | 개념 name+description만 (전문 청크 RAG 아님) |
| PDF 본문 저장 | `documents.raw_text`에 전체, 개념별 본문 컬럼 없음 |
| 개념 X 커리큘럼 분기 | strength&lt;0.5 → bridge; ≥0.5 → focused; 앎 → 자동 생략·수동 선택 학습 |
| bridge ≠ 선수만 | **선수 챕터 + 본문** 둘 다 |

### Cursor에서 완료한 코드 작업 (미커밋)

**Rename / 정렬**
- `materials` → `documents`, `markdown` → `raw_text`, `material_id` → `course_id`
- `concept_prerequisites` → `concept_edges`, `concept_masteries` → `concept_mastery`, `p_known` → `strength`, `depth` → `depth_level`

**신규**
- `users`, `courses`, `enrollments`, `auth` (default `dev@local`)
- `backend/alembic/versions/0009_team_schema_alignment.py`
- `frontend` documents 페이지, `flowStore` courseId

**삭제**
- `backend/app/features/materials/`, `frontend/features/materials/`

**프론트 라우트**
- `/lab/documents`, `/lab/diagnostic`, `/lab/curriculum`

### 미완 / 블로커
- Docker 미기동 시 `alembic upgrade head` 미실행
- ISSUE-001 BKT 버그 (rename 작업 부산물 추정)
- `seed`, `review` 스텁
- 학습 중 적응 루프 미구현

---

## 2026-06-30 전후 — Cursor — 인프라·문서 작업 (백필)

### 한 일
- DB 초기화·재기동 (`docker compose down -v`, up, alembic)
- MVP DB 스키마(8테이블) 문서화
- `docs/CLAUDE_CONTEXT.md` 최초 작성 (Cursor↔Claude 동기화용)
- 전체 흐름 mermaid 다이어그램 정리

---

## 의사결정 로그 (참고)

| 날짜 | 결정 | 이유 |
|------|------|------|
| 2026-06 | 팀원 스키마 **전체 이식 안 함** | MetaLearn은 JIT+BKT 중심, 4단 CMS·결제 등 제품 루프 밖 |
| 2026-06 | `materials` → `documents` 등 rename | 팀 스키마 1:1 동등 엔티티만 맞춤 |
| 2026-06 | `diagnostic_sessions` 유지 | 팀 스키마 `attempts` 통합은 출시 후보, 당장 교체 안 함 |
| 2026-06 | `curricula.blocks` JSON 유지 | 고정 교재 CMS 대신 JIT |
| 2026-07 | CONTEXT / WORK_LOG 분리 | 일지가 길어져 컨텍스트 오염 방지 |

---

## Git 스냅샷 (마지막 확인: 2026-07-02)

- **브랜치:** `feat/parsing` (= `origin/feat/parsing`, ahead/behind 없음)
- **마지막 커밋:** `5dbf7b9` feat: /lab 실험 플로우 — PDF 업로드, BKT 진단, JIT 커리큘럼
- **uncommitted:** documents 리네임, 0009 migration, auth, diagnostic/learning 수정 등 (ISSUE-002)
