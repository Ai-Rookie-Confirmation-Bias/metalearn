# MetaLearn — 서비스 현황 & 평가 (공유용)

> **작성**: 2026-07-06 · **관점**: `feat/backend-ai-core`(하류: 진단 후 학습) 중심, 서비스 전체 조망
> **한 줄 요약**: 핵심 학습 엔진(생성→검증→서빙→채점→국소화→선행삽입→커서)은 서버측에서 관통·검증됨. 다만 입구(진단·인증·업로드)가 비어 서비스 end-to-end는 아직 미완결.

---

## 1. 브랜치 지형

| 브랜치 | 내용 | 상태 |
|---|---|---|
| `feat/backend-ai-core` | 진단 **후** 하류 백엔드(학습 서빙·수준추적·살아있는 커리큘럼) | 커밋됨 (`1f0c0bf`) |
| `feat/parsing` | PDF 파싱·정제·씨앗·**진단평가** (상류) | 팀원 담당, 미완성 |
| `dev` | 프론트 본체(페이지 셸) + 정본 문서(SCHEMA/API.md) | 프론트 UI, 백엔드 스켈레톤 |
| `feat/front-learning` | 학습 화면 봉투 렌더러(registry) | dev+1, mock |
| `feat/integration-test` | (worktree) 우리 백엔드 + front-learning 프론트 조립 | 프론트 배선 진행, 로컬 테스트용 |

**경계**: 진단평가·수준 판정·씨앗 = **parsing**. "진단 후 → 커리큘럼 생성·서빙·수준추적" = **우리**.

---

## 2. 구현·검증 완료 ✅ (Docker + PostgreSQL E2E)

### 백엔드 — 핵심 학습 엔진
- **placement 수령**: 진단 floor/ceiling → `concept_mastery` 커리큘럼순 시딩 (`POST /courses/:id/placement`)
- **JIT 생성·검증·서빙**: 챕터 진입 → LLM 생성 → 근거 검증 게이트 → verified 봉투만, **정답 스트립** 서빙 (`/chapters/:id/generate`, `/sections/:id`)
- **인출 채점(서버)**: 클라 correct 무시, 서버 채점 → 숙련도·SM-2·다음행동 (`POST /attempts`)
- **원인 국소화(BKT×DAG)**: 실패 → `hold`(보류)/`prerequisite`(선수결손 blame)/`content`(본문결손)
- **선행 삽입**: cause=prerequisite → `chapters(origin=prereq)` 동적 삽입(멱등)
- **학습 커서**: 복귀 스택으로 선행 우회→복귀 자동화 (`learning_cursor`, `GET /courses/:id/cursor`)
- **책장·메타인지**: `GET /courses`(진행률·마지막활동), `GET /courses/:id/mastery`
- **절 잠금 서버 계산**: 트리 `SectionNode.locked`(순차 진행 규칙)

### 프론트 배선 (integration)
- 책장 · 학습(트리+절블록+attempts+JIT생성) · 분석(mastery)
- 블록 라운드트립 채점(mcq/cloze/explainBack) — 클라 판정 제거
- axios dev 인증헤더(임시)

### 아키텍처 원칙 정합 (README §2·§3)
> 클라는 **봉투 렌더러 조립 + attempt 제출 + 서버상태 미러**만. 생성·검증·채점·진행·완료·잠금·숙련도는 **전부 백엔드+DB**.
- 봉투(`{id,type,data,...}`) + `registry[type]` → 새 문제유형 = 렌더러 추가(마이그 0)
- 진행/완료/잠금 = 서버 진실 → React Query 미러. 클라엔 휘발성 UI(현재 절·입력값)만.

---

## 3. 아직 안 된 것 ⬜

| 영역 | 상태 | 담당 |
|---|---|---|
| 진단평가(floor/ceiling)·씨앗·개념그래프 | 미완성 | **parsing** |
| 소셜 로그인 / OAuth | 백·프론트 스텁, 임시 `X-User-Id` | 미착수 (ISSUE-005) |
| 수업 생성(`POST /courses`)·문서 업로드·파싱 | 미배선 | materials/parsing |
| 복습(`review/*`) | sm2 로직만, 라우터·서빙 없음 | 우리 |
| map / connections / 전용 progress 엔드포인트 | 없음 | 우리 |
| 오개념 감지 · cause=content 처방 · 선행 복귀 UI | 훅/부분 | 우리 |
| 로컬 EXAONE(오프라인) | Phase 2 스텁 | 후속 |

---

## 4. 리스크 & 열린 이슈

- **🔴 ISSUE-001 (최대 블로커)** — 우리(UUID) ↔ parsing(Integer) PK·마이그레이션 전면 분기. 실데이터 통합 불가. parsing과 **단독금지** 합의(정본 UUID로 스쿼시) 필요.
- **🟠 상류 공백** — 진단·인증·업로드 부재로 지금은 **시드 픽스처** 기반. 실사용 flow(가입→업로드→진단→학습) 미완결.
- **🟠 LLM 신뢰성** — faithfulness(ISSUE-003)·RAG(ISSUE-004) 미구현 → 생성 품질 보증 약함.
- **🟡 그래프 방향 규약** — parsing 규약 채택 확정, 소비자(우리) 정합 완료 (`GRAPH_ORIENTATION_CONTRACT.md`, ISSUE-012). 병합 시 parsing이 실제 그 규약대로 생산하는지 대조 필요.
- **🟡 배선 분산** — 프론트 배선 + 일부 백엔드 변경이 `feat/integration-test`(worktree)에 있음 → 최종엔 프론트 브랜치 / `backend-ai-core`로 정리 필요.

---

## 5. 종합 평가 (서비스 관점)

### 강점
- **제품의 심장이 돈다.** 생성→검증→서빙→채점→국소화→선행삽입→커서의 학습 루프가 서버측에서 실제로 관통·검증됨 — "GPT에 PDF 던지기"와 차별되는 핵심.
- **아키텍처 규율.** 봉투+registry, 서버가 진실, 프론트는 조립+미러 → 확장성 우수(새 문제유형=type 추가만).
- **계약 정합 + 배선 패턴 확립** → 남은 페이지 배선이 빠름.

### 약점 / 공백
- **수직 슬라이스 미완결.** 엔진은 도는데 **입구(가입·업로드·진단)와 출구(복습·공유)가 비어있음.** 현재는 데모(시드) 수준.
- **parsing 병합이 관문.** ISSUE-001이 안 풀리면 실데이터로 못 붙음.
- **생성 품질 보증 약함.** faithfulness/RAG 미구현.

### 성숙도
- **우리 구간(하류)**: MVP 완성·검증. 시드 기반 데모 가능.
- **전체 서비스**: **"핵심 엔진 완성, 양끝 미완"** — 알파 이전.

### 우선순위 제안
1. **parsing 병합 합의(ISSUE-001)** — 실데이터 통합의 관문, 가장 급함
2. **진단 → placement 실연결** — 지금 placement는 "수령"만, 진단이 없어 반쪽
3. **최소 인증** — OAuth 또는 `X-User-Id` 유지 결정
4. **나머지 페이지 배선**(생성 위저드·복습) + worktree 변경 정리

---

## 참고 문서
- `docs/CLAUDE_CONTEXT.md` — 제품·아키텍처·원칙·인터페이스 계약 (헌법, 로컬)
- `docs/WORK_LOG.md` — 세션별 작업·결정·검증 (로컬)
- `docs/GRAPH_ORIENTATION_CONTRACT.md` — 지식그래프 방향 규약 (parsing 합의용)
- `dev/docs/SCHEMA.md`, `dev/docs/API.md` — 정본 스키마·API 명세
