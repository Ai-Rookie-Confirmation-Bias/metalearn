# docs 문서 지도

## 어디부터 읽나

- **★ integration 브랜치를 처음 켜는 사람** → **[INTEGRATION.md](INTEGRATION.md)**
  — 무엇이 합쳐졌나 · 5분 안에 띄우기 · 실제로 도는 API · 각자 할 일
- **★ 데모를 준비하는 사람** → **[DEMO.md](DEMO.md)**
  — **3분 대본** · 사전 준비 체크리스트 · 위험/대비
- **문제 생성을 이어서** → [QUIZ.md](QUIZ.md)(설계) → [QUIZ_TUNING.md](QUIZ_TUNING.md) 맨 위 "지금 유효한 결론" → [WORKLOG.md](WORKLOG.md)
- **학습 커리큘럼을 이어서** → [LEARNER_CONTRACT.md](LEARNER_CONTRACT.md)(계약) → [WORK_LOG.md](WORK_LOG.md)(일지)
- **파싱을 이어서** → [STATUS.md](STATUS.md)(항목별 현황이 기준) → [PARSING_v3.md](PARSING_v3.md)
- **파싱 → 문제은행 입력 형식** → [QUIZ_INPUT.md](QUIZ_INPUT.md)
  (변환기는 이미 있다: `backend/app/features/quiz/adapters/parsing_tree.py`)

## 파일별 역할

### 문제 생성 기능 (quiz)

| 파일 | 역할 | 성격 |
| --- | --- | --- |
| [QUIZ.md](QUIZ.md) | 파이프라인 설계 — 왜 이 구조인가, 단계별 책임, UX 결정(§3.5 격리 선긋기·§3.6 기출 모드), 미확정 협의 목록 | 설계서 (결정이 바뀔 때만 수정) |
| [QUIZ_INPUT.md](QUIZ_INPUT.md) | 파싱 결과 JSON 입력 계약 — 팀원과의 인터페이스 | 계약서 (팀원 협의로만 수정) |
| [QUIZ_TUNING.md](QUIZ_TUNING.md) | 품질 실측 기록 (스모크 1~12회차) — 발견한 결함 패턴과 대응의 근거. 맨 위 "지금 유효한 결론"만 읽어도 됨 | 실험 노트 (시간순 누적) |
| [WORKLOG.md](WORKLOG.md) | 세션별 작업 일지 + 현재 상태 + 다음 작업 + 사고 이력 | 일지 (세션마다 누적) |
| 문제_생성_검증_파이프라인.docx | 생성·검증 단계별 설명서 (읽기용 배포 문서, md 내용의 정리본) | 산출물 (커밋 안 함) |

### 통합

| 파일 | 역할 | 성격 |
| --- | --- | --- |
| [INTEGRATION.md](INTEGRATION.md) | 세 브랜치가 합쳐진 상태 — 실행법, 실제 API, 어디까지 이어졌나, 각자 할 일 | 안내서 (합칠 때마다 갱신) |
| [DEMO.md](DEMO.md) | 3분 데모 대본 — 네 장면 · 사전 준비 · 위험 | 시연 대본 |

### 파싱 기능 (seedParsec)

| 파일 | 역할 | 성격 |
| --- | --- | --- |
| [PARSING_v3.md](PARSING_v3.md) | 파싱 v3 설계 — 문서 → 목차·조각·문장·개념 | 설계서 |
| [PARSING_PLAN.md](PARSING_PLAN.md) | 단계별 작업 계획 (번호가 STATUS의 항목 번호) | 계획서 |
| [STATUS.md](STATUS.md) | 항목별 완료/미완 현황 — **무엇이 실제로 되는지는 여기가 기준** | 현황 |

### 학습 기능 (curriculum)

| 파일 | 역할 | 성격 |
| --- | --- | --- |
| [LEARNER_CONTRACT.md](LEARNER_CONTRACT.md) | 학습층 스키마·API 계약 (구현된 코드 기준으로 작성) | 계약서 |
| [WORK_LOG.md](WORK_LOG.md) | 학습층 작업 일지 + 회의 기록 | 일지 |

> ⚠️ **`WORKLOG.md`(quiz)와 `WORK_LOG.md`(학습)는 다른 파일이다.** 이름이 한 글자
> 차이라 서로 덮어쓰기 쉽다. 통합에서 둘 다 살렸고, 합칠지 이름을 바꿀지는
> 정해야 한다.

### 프로젝트 공용

| 파일 | 역할 |
| --- | --- |
| [API.md](API.md) | ⚠️ **2026-07-03 = 피벗 전.** 초기 설계 기록으로만. 실제 API는 [INTEGRATION.md §3](INTEGRATION.md) |
| [SCHEMA.md](SCHEMA.md) | ⚠️ **2026-07-03 = 피벗 전.** 실제 스키마는 `backend/alembic/versions/`가 정본 |
| [folder.md](folder.md) | ⚠️ 같은 07-03 문서. 프론트엔드 폴더 구조 |

> 위 셋은 네 브랜치 모두 같은 blob이고 아무도 안 고쳤다. **새 내용을 여기에 추가하지
> 않는다** — 유효한 것과 아닌 것이 섞이면 둘 다 못 믿게 된다.

## 문서 규칙

- 새 결정은 **QUIZ.md**(무엇을/왜), 실측 근거는 **QUIZ_TUNING.md**(어떻게 확인했나),
  작업 이력은 **WORKLOG.md**(언제/어느 세션에서) — 같은 내용을 세 곳에 다 쓰지 말고
  한 곳에 쓰고 나머지는 링크로 가리킨다.
- 날짜는 상대 표기("어제") 금지, 절대 날짜(08-06)로.
