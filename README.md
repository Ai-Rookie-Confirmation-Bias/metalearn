# MetaLearn

교재를 분석해 학습자에게 **부족한 선행 개념**을 찾고, 그 개념을 단원으로 만들어 **개인 목차에 추가하는** 학습 플랫폼입니다.

같은 교재를 골라도 진단 결과가 다르면 목차가 달라집니다. 교재에 없는 선행 개념이라도 단원으로 만들어 목차 앞에 붙이고, 학습 기록은 개념 단위로 쌓여 다음 설명의 분량과 복습 시점을 정합니다.

**2026 인공지능 루키 본선 진출** (과학기술정보통신부 주최 · 국내 AI 트랙). 수상이 아니라 본선 진출입니다.

---

## 무엇을 하는가

| 단계 | 하는 일 |
| --- | --- |
| 교재 준비 | 강의자료 업로드 또는 도서관에서 선택 → 개념 추출 |
| 부족한 지식 확인 | 아는 개념 체크 → 확인 문항 → 설명 방식 선택 |
| 목차 확정 | 부족한 개념을 단원으로 만들어 목차 앞에 추가 |
| 학습 | 설명 → 답해 보기 반복. 모르는 문장을 선택하면 그 자리에서 설명 |
| 복습·평가 | 단원 끝 형성평가, 잊을 때쯤 복습 |
| 문제집 | 학습과 **분리된** 문제은행. 학습 기록을 참조하지 않음 |

선수 개념 판정은 임베딩 유사도로 확실한 구간을 먼저 가르고, 애매한 구간만 LLM에 다시 물어 "가르치는 개념인지 전제하는 개념인지" 확인합니다. 목차·분량·복습 시점 같은 결정은 LLM이 아니라 규칙 엔진이 맡습니다.

## 실행

```bash
cp backend/.env.example backend/.env   # 키 채우기
docker compose up -d                   # db · backend · frontend
docker compose exec backend alembic upgrade head
```

`backend/.env`에 필요한 키는 `backend/.env.example`에 이름만 들어 있습니다.

## 아키텍처

```
backend/  FastAPI · Python 3.12 · uv
  app/core/      config · database · deps · security
    llm/         base · solar · exaone
    quality/     checks · grading · parsing · prompts · validator
  app/features/  auth · course · curriculum · learning · materials
                 parsing · quiz · review · seed
  alembic/       마이그레이션 12개 (head: 0012_document_kind_exam_style)
  tests/         테스트 파일 25개
frontend/ React 19 · Vite 6 · TypeScript 5.7 · pnpm
  src/pages/     화면 19개
  상태: TanStack Query 5 (서버) · Zustand 5 (UI)
  스타일: Tailwind CSS 4 · Phosphor Icons
db/       PostgreSQL 16 + pgvector
```

| 구분 | 사용 모델 |
| --- | --- |
| 문서 파싱 | Upstage Document Parse |
| 개념 추출 · 설명 생성 · 문항 생성 · 선수 판정 재질의 | Upstage Solar Pro 3 |
| 선수 판정 1차 계산 · 근거 검색 | Upstage Solar Embedding |
| 문항 교차 검증 | LG AI 연구원 K-EXAONE |

문항은 만든 모델과 검증하는 모델을 다르게 두었습니다(`quiz/service.py`). `EXAONE_API_KEY`가 없으면 생성 모델이 검증까지 겸합니다(`quiz/router.py`의 `_verify_llm`).

## 검증 상태

컨테이너에서 측정한 값입니다.

| 항목 | 결과 |
| --- | --- |
| 백엔드 테스트 | `pytest` 344개 전부 통과 |
| 프론트엔드 타입 검사 | `tsc --noEmit` 오류 없음 |

## 팀 구성과 담당

3인 팀입니다. 아래 라인 수는 `git blame -w`로 `integration` 브랜치를 실제 집계한 값이며, 추정치가 아닙니다.

| 담당 | 영역 | 경로 | 라인 | 본인 비율 |
| --- | --- | --- | --- | --- |
| **박지성** | 자료 파싱 → 코스 생성 | `backend/app/features/parsing` | 7,376 | 98% |
| | | `backend/app/features/course` | 4,123 | 96% |
| | | `backend/alembic` | 961 | 78% |
| | | `backend/app/core/llm` | 420 | 70% |
| **윤현석** | 진단 이후 커리큘럼 결정 로직 · 규칙 엔진 · pytest | `backend/app/features/curriculum` | 6,798 | 91% |
| | | `backend/bench` | 1,713 | 100% |
| | | `backend/tests` | 5,746 | 46% |
| | | `backend/app/features/auth` | 354 | 99% |
| **소민섭** | 문제 생성 및 검증 | `backend/app/features/quiz` | 2,082 | 41% |
| | | `backend/app/core/quality` | 1,011 | 100% |

프론트엔드는 셋이 함께 작업했습니다.

| 경로 | 라인 | 박지성 | 윤현석 | 소민섭 |
| --- | --- | --- | --- | --- |
| `frontend/src/pages` | 8,479 | 44% | 31% | 25% |
| `frontend/src/features` | 4,828 | 48% | 51% | 0% |

전체 코드 44,717줄 기준으로는 박지성 46% · 윤현석 39% · 소민섭 12%입니다.

## 브랜치

- **`dev`** — 기본 브랜치입니다.
- **`integration`** — 실제 개발이 진행된 브랜치입니다. 세 사람의 기능 브랜치(`feat/*`)를 여기로 모았습니다.
- `main`은 2026-06-16 초기 골격에서 멈춰 있고 사용하지 않습니다.

## AI 코딩 도구 사용

이 프로젝트는 AI 코딩 도구(Claude Code)를 사용해 개발했고, 커밋 이력에 그 흔적이 남아 있습니다.

- `integration` 브랜치 205개 커밋 중 **115개(56%)**에 `Co-Authored-By: Claude` 트레일러가 있습니다.
- 도구를 커밋 작성자로 둔 커밋이 **6개** 있습니다. 문제은행 백엔드 초기 구현과 설계 문서 커밋입니다.
- `git blame` 기준으로 도구 명의 라인은 전체 코드의 **4%**(1,690 / 44,717줄)입니다. 문제은행 기능(`features/quiz`)에서는 47%로 가장 높습니다. 이 중 1,116줄은 테스트 픽스처 JSON 한 개입니다.

## 알려진 한계

- **문항 교차 검증이 조건부입니다.** `EXAONE_API_KEY`가 없으면 생성 모델이 검증까지 겸합니다. 얼마나 걸러 내는지는 아직 측정하지 않았습니다.
- **실사용자 테스트가 없습니다.** 팀 내부 실행으로만 확인했습니다.
- **컴퓨터공학 자료로만 검증했습니다.** 다른 분야 자료에서 개념 추출·진단 정확도를 확인하지 않았습니다.
- **닉네임 저장이 연결되지 않았습니다.** `frontend/src/pages/ProfileSetupPage.tsx`에 미연결 표시가 남아 있습니다.
- **`UXUI_ANT/`는 대회 전 정적 목업입니다.** 현재 프론트엔드와 별개이며 실행 경로에 포함되지 않습니다.
- **오프라인 동작은 구현하지 않았습니다.** 초기 설계에는 있었으나 1차 개발 기간에는 학습 파이프라인 완성에 집중했습니다. `frontend`에 `dexie` 의존성이 남아 있는 것은 그 흔적입니다.
