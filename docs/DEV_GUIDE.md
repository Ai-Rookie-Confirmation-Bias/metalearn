# MetaLearn — 개발 온보딩 가이드

> **이 브랜치 `feat/yoonhs-integration` = 팀원+나 병합 최신 통합본 (분기점).**
> 여기서 기능 브랜치를 짧게 따서 개발하고 바로 다시 머지한다. "우리 서비스가 뭔가"는 [`SERVICE_OVERVIEW.md`](./SERVICE_OVERVIEW.md), DB는 [`SCHEMA.md`](./SCHEMA.md) 참조.
> ※ `WORK_LOG.md`·`CLAUDE_CONTEXT.md`는 **각자 세션/작업 로그**(개인용) — 공유 이해는 이 문서와 SERVICE_OVERVIEW를 기준으로 한다.

---

## 0. 브랜치 규율 (합의)

- **통합 브랜치 하나** = `feat/yoonhs-integration`. 항상 여기가 최신 병합본.
- **기능은 짧게 따서 바로 머지.** 2주짜리 장기 분기 금지(이번에 병합 지옥을 겪은 교훈). 하루~며칠 단위 feature 브랜치 → 통합 브랜치로 즉시 머지.
- 팀원도 **이 브랜치에서 분기**해서 작업 시작.
- **마이그레이션 스쿼시(0001~0019 → 단일 0001)**: ISSUE-001. 아직 안 함 — **소민섭과 동시에** 진행해야 안전(단독 금지). 통합 브랜치가 안정되면 함께.

---

## 1. 지금 이 브랜치에 뭐가 있나 (병합 이력)

`feat/yoonhs-integration` = 기존 통합본 + **소민섭의 진단 재설계**(`redesign/diagnostic-profiling`, 2026-07-10 병합):
- `4531f31` 진단 재설계 — 온보딩(성향+기반지식) + 복습 루프 + 책장 diag_status
- `b7e2706` 학습 확인 루프 — 「풀면 진행」 게이트 + cloze 빈칸별 채점 + 정답 공개
- `9c3c608` 공유 문서 추적 편입

---

## 2. 구현 상태 (2026-07-10, 병합 후)

| 상태 | 항목 | 출처 |
|---|---|---|
| ✅ 동작 | 다중 PDF 1:N 통합 · ingest→개념그래프→커리큘럼 · JIT 생성(티칭 먼저) · faithfulness 게이트 · 서버 채점·치팅 방어 · BKT 국소화·선행 삽입·복귀 커서 · SM-2 복습 | yoonhs |
| ✅ 동작 | **성향 진단 온보딩(3축 프로파일)** · **기반지식 갭+선수 에지 역주입** · **첫 생성 성향 지시문 주입** · **오답노트 weaving(복습 섹션 맨 앞)** · **진단↔커리큘럼 분리(diag_status)** · 학습 확인 루프(풀면 진행) | **소민섭** |
| ✅ 동작(별 트랙) | 온디바이스 EXAONE 1.2B 데모(채점·꼬리질문) | yoonhs (`feat/ondevice-exaone-mvp`) |
| 🔨 다음 | 빠른 완료(인출 2연속=완료) · 학습 캔버스 1차(트리 시각 개선+이유 라벨) · localize 증거 기반화 | — |
| 📋 백로그 | 채점 견고성+레이트리밋 · 병렬 ingest+스트리밍(속도) · 학습 캔버스 2·3차(개념지도·diagram) · 비용 지표 · OAuth 병합(`feat/oauth-login`) · **마이그 스쿼시** | — |

> 성향 진단 = **소민섭 작업**. 절대 yoonhs 작업과 혼동 금지.

---

## 3. 백엔드 모듈 맵 (`backend/app/features/`)

| 모듈 | 역할 |
|---|---|
| `documents/` | PDF ingest 파이프라인 (파싱→정제→청킹→개념추출→그래프). **속도 병목 여기**(개념추출 동시성 3·문서 순차) |
| `seed/` | ingest 후 커리큘럼 트리 빌드(`build_tree`) · `finalize_onboarding`(전 절 todo 시딩+갭+역주입) · `refs.py`(external_refs) |
| `curriculum/` | 위상정렬 커리큘럼 + `GET /courses/:id` 트리 API (⚠️ 엣지 미포함 — 개념지도 시각화 시 확장 필요) |
| `diagnostic/` | **`onboarding.py`**(성향+기반지식 3단계 상태기계: disposition→probe→quiz) |
| `profile/` | **성향 프로파일(소민섭)** — `learner_profiles`(mig 0019), 3축 EMA, 결정적 생성 지시문, `GET/PATCH /api/profile/me` |
| `learning/` | JIT 블록 생성(`generator.py`) · faithfulness · 서버 채점(`grading.py`) · BKT 국소화(`localization.py`) · 다음 액션 |
| `review/` | SM-2 간격 반복(`sm2.py`) |

**프론트(`frontend/src/`)**: `pages/`(URL 1:1) + `features/{diagnostic,learning,review,...}`. 블록 봉투 렌더러 = `features/learning`. 시각 블록(chart·conceptMap 등)은 카탈로그(`UXUI_BRIEF.md`)에 설계만 — 라이브 미이식.

---

## 4. 실행 (WSL, Docker `mlv2` 스택)

```bash
# docker 자격증명 우회(이 PC 필수)
mkdir -p /tmp/dockercfg && echo '{}' > /tmp/dockercfg/config.json

cd /home/yoonhs/metalearn-placement
DOCKER_CONFIG=/tmp/dockercfg docker compose -p mlv2 -f docker-compose.yml -f docker-compose.trial.yml up -d --build
DOCKER_CONFIG=/tmp/dockercfg docker compose -p mlv2 exec -T backend uv run alembic upgrade head   # → 0019
```
- 포트: backend `58001` / frontend `55173`. 볼륨 마운트라 소스 수정은 HMR 즉시 반영.
- 패키지 추가 시엔 `docker compose build frontend`(컨테이너 node_modules는 익명 볼륨).
- `.env`는 gitignore → 워크트리마다 없으면 메인에서 복사.

---

## 5. 마이그레이션 상태

- 체인: `0001 → … → 0016 → 0018 → 0019`(단일 head, 0017 번호만 결번·끊김 없음). 신규 = `0019_learner_profiles`(성향).
- **스쿼시(단일 0001화)는 소민섭과 함께** — ISSUE-001, 단독 금지.

---

## 6. 관련 문서

- [`SERVICE_OVERVIEW.md`](./SERVICE_OVERVIEW.md) — 서비스 정의(제안서 대비 진화·3레이어 맞춤·역할분리)
- [`SCHEMA.md`](./SCHEMA.md) — DB 스키마(정본)
- [`UXUI_BRIEF.md`](../UXUI_BRIEF.md) — 블록 컴포넌트 카탈로그(40+)
- `WORK_LOG.md` / `CLAUDE_CONTEXT.md` — 세션/작업 로그(개인용, 공유 기준 아님)
