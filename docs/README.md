# docs 문서 지도

## 어디부터 읽나

- **처음 온 사람** → [QUIZ.md](QUIZ.md) (설계) → [QUIZ_TUNING.md](QUIZ_TUNING.md) 맨 위 "지금 유효한 결론"
- **이어서 작업하는 세션** → [WORKLOG.md](WORKLOG.md) "현재 상태 · 다음 작업 · 주의사항"
- **파싱 담당 팀원** → [QUIZ_INPUT.md](QUIZ_INPUT.md) (보내야 할 JSON 형식)

## 파일별 역할

### 문제 생성 기능 (quiz)

| 파일 | 역할 | 성격 |
| --- | --- | --- |
| [QUIZ.md](QUIZ.md) | 파이프라인 설계 — 왜 이 구조인가, 단계별 책임, UX 결정(§3.5 격리 선긋기·§3.6 기출 모드), 미확정 협의 목록 | 설계서 (결정이 바뀔 때만 수정) |
| [QUIZ_INPUT.md](QUIZ_INPUT.md) | 파싱 결과 JSON 입력 계약 — 팀원과의 인터페이스 | 계약서 (팀원 협의로만 수정) |
| [QUIZ_TUNING.md](QUIZ_TUNING.md) | 품질 실측 기록 (스모크 1~12회차) — 발견한 결함 패턴과 대응의 근거. 맨 위 "지금 유효한 결론"만 읽어도 됨 | 실험 노트 (시간순 누적) |
| [WORKLOG.md](WORKLOG.md) | 세션별 작업 일지 + 현재 상태 + 다음 작업 + 사고 이력 | 일지 (세션마다 누적) |
| 문제_생성_검증_파이프라인.docx | 생성·검증 단계별 설명서 (읽기용 배포 문서, md 내용의 정리본) | 산출물 (커밋 안 함) |

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
| [API.md](API.md) | 서비스 전체 API 명세 |
| [SCHEMA.md](SCHEMA.md) | DB 스키마 (PostgreSQL) — ⚠️ 피벗 전 문서라 현재 코드와 다르다 |
| [folder.md](folder.md) | 프론트엔드 폴더 구조 안내 |

## 문서 규칙

- 새 결정은 **QUIZ.md**(무엇을/왜), 실측 근거는 **QUIZ_TUNING.md**(어떻게 확인했나),
  작업 이력은 **WORKLOG.md**(언제/어느 세션에서) — 같은 내용을 세 곳에 다 쓰지 말고
  한 곳에 쓰고 나머지는 링크로 가리킨다.
- 날짜는 상대 표기("어제") 금지, 절대 날짜(08-06)로.
