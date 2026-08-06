# MetaLearn — API 명세 (🔒 = 인증 필요)

> README.md에서 분리. **API 변경은 이 파일에서 관리한다.**


공통: `Authorization: Bearer <token>` · 에러 `{error:{code,message}}` · 목록 `?cursor=&limit=`

### 인증/유저

| M | 경로 | 용도 |
| --- | --- | --- |
| GET | /auth/{provider}/login | 소셜 로그인 시작 — 구글/네이버 동의 화면으로 리다이렉트 (`{provider}`=google\|naver) |
| GET | /auth/{provider}/callback | 콜백: 코드 교환 → 유저 생성/조회 → 세션·토큰 발급 (신규면 프로필 설정으로) |
| POST | /auth/refresh | accessToken 갱신 |
| POST | /auth/logout 🔒 | 로그아웃 |
| GET | /me 🔒 | 내 정보 |
| PATCH | /me 🔒 | 프로필 수정(닉네임 등) |
| GET | /me/stats 🔒 | 대시보드 통계(streak/시간/목표율) |

### 자료/코스

| M | 경로 | 용도 |
| --- | --- | --- |
| POST | /documents 🔒 | 자료 업로드(`kind` 지정) → {documentId, status}. link는 파일 대신 URL |
| GET | /documents/:id 🔒 | 처리 상태 폴링 |
| POST | /courses 🔒 | 자료 선택으로 코스 생성. body `{documentIds[], primaryIds[], purpose}` → course + course_documents(메인/보조·순서) + enrollment(purpose) 생성 + 씨앗 트리거 |
| GET | /courses 🔒 | 내 책장 — 코스별 진행률 + `lastActivityAt`(=`MAX(attempts.created_at)`, 저장 아닌 계산값) 포함 |
| GET | /courses/:id 🔒 | 챕터/절 트리 |
| GET | /courses/:id/map 🔒 | 전체 지도(개념 그래프) |
| DELETE | /courses/:id 🔒 | 삭제 |

### 진단/생성/학습

| M | 경로 | 용도 |
| --- | --- | --- |
| POST | /courses/:id/diagnostic 🔒 | 진단 시작 → {next(블록 봉투)} (enrollments.diag_* 갱신) |
| POST | /courses/:id/diagnostic/answer 🔒 | 응답 → attempts(diagnostic) 기록 → 다음/종료(floor, ceiling) |
| POST | /chapters/:id/generate 🔒 | JIT 생성 트리거(생성+검증, 선행은 외부 근거 검색) |
| GET | /chapters/:id 🔒 | 생성 상태 폴링(gen_status) |
| POST | /sections/:id/confidence 🔒 | 확신도 → variant |
| GET | /sections/:id 🔒 | 절 블록 로드(verified 봉투[], 출처 배지 포함) |

### 인출/진행/복습/연결

| M | 경로 | 용도 |
| --- | --- | --- |
| POST | /attempts 🔒 | 정답 기록. explainBack이면 {score, feedback, missedPoints} 반환 |
| GET | /courses/:id/progress 🔒 | 완료/잠금 계산 |
| GET | /courses/:id/mastery 🔒 | 개념별 숙련도(메타인지 분석) |
| GET | /review/due?courseId= 🔒 | 복습 도래 개념 + reviewGate |
| POST | /review/answer 🔒 | 복습 응답 → 간격 갱신(attempts kind=review) |
| GET | /review/schedule?courseId= 🔒 | 복습 캘린더 |
| GET | /courses/:id/connections 🔒 | 연결 퀴즈 소집 |

### 문제은행 (문제 페이지 — 학습 데이터와 격리, docs/QUIZ.md)

| M | 경로 | 용도 |
| --- | --- | --- |
| POST | /courses/:id/quiz/generate | 파싱 결과(JSON)로 문제은행 배치 생성 → {saved, discarded[]}. 파싱 완료 시 내부 트리거 예정 |
| GET | /courses/:id/quiz 🔒 | 문서별·목차별 문항 수 (범위 선택 화면) |
| POST | /courses/:id/quiz/session 🔒 | {documentId, tocIndexes[], count} → 문항 샘플링 (정답·해설 제외) |
| POST | /quiz/attempts 🔒 | 답 제출 → 서버 채점 → {correct, answer, explanation(고른 선지 해설), evidence(근거 원문+페이지)} |

### 결제/구독

| M | 경로 | 용도 |
| --- | --- | --- |
| GET | /billing/plans | 요금제 목록 |
| GET | /me/subscription 🔒 | 내 구독 상태 |
| POST | /billing/checkout 🔒 | 결제 세션 생성 → {checkoutUrl} |
| POST | /billing/cancel 🔒 | 구독 취소 |
| POST | /billing/webhook | 프로바이더 웹훅(서명 검증, 인증X) |

### 알림

| M | 경로 | 용도 |
| --- | --- | --- |
| GET | /notifications 🔒 | 알림 목록 |
| POST | /notifications/:id/read 🔒 | 읽음 |
| POST | /notifications/read-all 🔒 | 전체 읽음 |
| POST | /me/push-tokens 🔒 | 기기 토큰 등록 |
| DELETE | /me/push-tokens/:id 🔒 | 토큰 해제 |
