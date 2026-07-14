# WORK_LOG — feat/yoonhs-integration

> 세션 블록은 맨 위에 append. 최신이 위.

---

## 2026-07-08 · 배치고사 UI 전환 + 다중 PDF 통합 + 방향 재점검

**베이스**: `trial/full-assembly-v2`(parsing 팀 v2) → 새 브랜치 `feat/yoonhs-integration`
(원래 `feat/placement-ui`로 만들었다가 통합본이라 rename)

### 사용자 요청 (시간순)
1. v2 리뷰 + 실제 구동 확인
2. 진단 UI를 v2 배치고사(placement)로 전환
3. 학습 콘텐츠 설명이 너무 얇음 → 보강
4. 다중 PDF를 순서대로 한 코스로 (정석 1:N)
5. 코스 이름 직접 입력
6. 선행학습을 명시적으로(배지/배너, 어느 본편 준비인지)
7. 진단 결과가 어디에 근거로 들어가는지 + 회의 방향과의 정합성 점검

### 한 일 (커밋)
- `30000ee` 진단 UI → v2 배치고사(`/diagnostic/placement/*`)로 전환. 문항별 피드백 없이 즉시 다음 문항.
- `13f0675` 개념 설명 보강: 프롬프트 "티칭 먼저→인출 나중", faithfulness 게이트 완화(모순·날조만 차단). 원문 발췌 800→1500.
- `936b702` **다중 PDF 통합(1:N)**: Document에 course_id/seq/role(마이그 0018), 배치 업로드(`/upload-batch`), build_tree/placement/RAG를 다중문서로, 슬러그 충돌 방지.
- `9fff509` 코스 이름 직접 입력(비우면 첫 파일명).
- `d9acfb5` 챕터 재생성 FK 크래시 픽스(이미 푼 블록 attempts 먼저 삭제).
- `ef439de` 선행학습 명시화: 사이드바 "선행" 배지 + "↳ 본편 준비" + 진입 안내 배너.

### 결과 / 검증
- 4-PDF 배치 업로드 E2E 통과: 380개념·25챕터, 트리가 문서순(ch01→04)으로 stacking, 배치고사·학습 정상.
- 프론트 tsc 0. 단일 PDF 경로 하위호환 유지.
- 스택: mlv2(`docker-compose.trial.yml`), backend 58001 / frontend 55173.

### 추론·결정 (중요)
- **구현이 회의 방향과 엇갈림을 발견** → 방향 재회의 필요.
  - 회의: 성향 진단 + 풀컨텍스트+성향맞춤 + 인출을 "복습 시점"에 오답노트로 반영, 반복진단 지양.
  - 구현: **수준(floor/ceiling)** 배치고사 + mastered/locked로 커리큘럼 축소 + **실시간 BKT** 추적. 성향·오답노트 weaving 없음.
- 방향 정리 문서: `METALEARN_방향정렬.md` (노션 공유용, 현황+대조표+회의 안건).

### 열린 이슈 / 다음 액션
| # | 항목 | 상태 |
|---|---|---|
| 1 | **방향 재회의** — 성향 진단 / 수준 반영 타이밍(실시간 vs 복습) / 커리큘럼 축소 유지 / 진단-커리큘럼 분리 | ⏸ 회의 대기 |
| 2 | 위키 429 → external_refs LLM 폴백 과다(web 17/llm 69) — refs.py rate-limit 개선 | 미착수 |
| 3 | 문서 병렬 ingest(속도) — 지금 순차, Solar 8슬롯 중 3만 사용 | 미착수 |
| 4 | LearningPage가 courses[0]만 봄 — 클릭한 코스로 라우팅(`/learning/:courseId`) | ✅ 해결(2026-07-14: 라우트 추가 + 책장 링크 코스별 + 코스 전환 시 절 선택 리셋) |
| 5 | 진단 미완료 코스 트리 400 (ceiling 없음) — 논점 4와 연결 | 미착수 |
| 6 | Document 스키마 변경(course_id/seq/role)은 parsing 팀 영역 → 병합 시 조율 | 협의 |

### 별개 브랜치
- `feat/oauth-login`: Google/Naver OAuth 코드 완성(자격증명만 남음). 이번 통합본과 분리.
