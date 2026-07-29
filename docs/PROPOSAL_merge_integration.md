# 안건: integration 백엔드 자산을 dev로 병합하기

작성 2026-07-29 · 근거는 전부 실제 브랜치 대조 결과(추정 아님)

---

## 0. 한 줄 안건

**서비스 방향(문제은행형 CBT)은 그대로 간다. 다만 그것을 _처음부터 만들 것인지_,
`feat/yoonhs-integration`에 이미 있는 엔진 위에 올릴 것인지를 정하자.**

- 바꾸자는 것: 작업 **베이스**
- 안 바꾸는 것: 서비스 정의, 4에이전트 분담, 각자 브랜치

---

## 1. 왜 지금 이 얘기를 하는가

문제 생성 에이전트를 dev 기준으로 구현하면서, **오늘 하루를 들여 만든 "원문 근거 대조"가
integration에 이미 `faithfulness 게이트`로 구현되어 있다는 걸 발견**했다.
같은 일이 다른 에이전트에서도 반복될 가능성이 크다.

---

## 2. 확인된 사실 (2026-07-29 브랜치 대조)

기준: `origin/dev = ebfb65d` / `feat/yoonhs-integration = d777539` / 분기점 `d98d95a`
커밋 차이: **dev-only 1개(머지 커밋), integration-only 119개**

### 2-1. 병합 비용

| 항목 | 결과 |
|---|---|
| **같은 파일을 양쪽이 수정한 건수** | **0건** |
| integration이 추가하는 변경 | 217 files, +29,562 lines |

→ **충돌 후보가 0건이다.** 병합 난이도를 이유로 미룰 근거가 없다.

### 2-2. 두 브랜치의 실제 내용물

| | dev | integration |
|---|---|---|
| backend features | 5개 (auth, learning, materials, review, seed) | **9개** (+ curriculum, diagnostic, documents, profile) |
| **DB 마이그레이션** | **1개** | **22개** |
| 프론트 학습 블록 | 8개 | **13개** (+ EvidenceBadge, Table, Diagram, Image, Analogy) |

→ **dev의 백엔드는 스키마가 사실상 없는 상태**다. dev 기준으로 간다는 것은
백엔드 도메인을 처음부터 다시 만든다는 뜻이다.

### 2-3. 새 방향(문제은행)이 요구하는 기능의 소재

| 새 계획에서 필요한 것 | dev | integration | 파일 |
|---|:---:|:---:|---|
| 원문 대조(=검증 에이전트 핵심) | ❌ | ✅ | `backend/app/core/verify_grade.py` |
| 근거 원문 조회 API(근거배지) | ❌ | ✅ | `backend/app/features/learning/router.py` |
| 문항 정답유출 방어 | ❌ | ✅ | `backend/app/features/learning/generator.py` |
| 잠금(locked) 계산 = 레벨 게이트 원형 | ❌ | ✅ | migration `0012_blueprint_schema` |
| 선행 개념 삽입 | ❌ | ✅ | migration `0007_prerequisite_sessions` |
| 복습 스케줄(SM2) | ❌ | ✅ | `backend/app/features/learning/policy.py` |
| RAG 임베딩 검색 | ✅ | ✅ | 양쪽 다 존재 |

> 미확인: "개념 그래프"는 검색 패턴으로 양쪽 모두 미검출 — 코드상 다른 이름일 수 있어
> 이 항목은 확인 전까지 근거로 쓰지 않는다.

---

## 3. 제안하는 형태 — "부품은 그대로, 순서만 뒤집기"

멘토링에서 합의한 방향(문제은행 · 레벨 · CBT)을 **유지**하되, 구현은 기존 엔진 재사용.

| | 기존 | 진화형 |
|---|---|---|
| 학습 진입 | 진단 퀴즈로 수준 파악 | ❌ 제거 → **바로 문제 풀이** |
| 학습 단위 | 절(설명+문항 묶음) | **문항** |
| 진행 순서 | 커리큘럼 순차 | **셔플 + 레벨 게이트** |
| 설명 블록 | 먼저 읽음 | **틀렸을 때 열림** (재사용) |
| 근거배지 · faithfulness · 선행삽입 · SM2 | 있음 | **그대로 재사용** |

버리는 것은 **진단 퀴즈**와 **순차 진행** 두 가지뿐이다.

> 이는 제안서 1.6에서 이미 선언한 방향과 일치한다 —
> *"1회성 진단은 오채점 하나로 커리큘럼 전체가 무너져, 맞춤은 스냅샷이 아니라 상시 갱신이어야 한다."*
> 진단 퀴즈를 없애고 매 문항을 평가 신호로 쓰는 것이 그 문장의 완성형이다.

---

## 4. 담당별 영향 — 아무도 작업을 잃지 않는다

| 담당 | 변화 |
|---|---|
| **파싱** | 그대로. 챕터 단위 뭉치기 + 원문 보존 |
| **생성** | 그대로. 기존 `generator.py`를 문제은행형으로 **확장** |
| **검증** | 그대로 + **유리해짐**. faithfulness를 출발점으로 받고, 없는 것(정답유출·중복검사)만 추가 |
| **진도** | 그대로. 레벨 게이트 + 셔플 (기존 잠금 로직 참고 가능) |

4에이전트 구조와 개인 브랜치는 유지된다. 바뀌는 것은 **베이스뿐**이다.

---

## 5. 결정이 필요한 것

1. **integration 백엔드 자산을 dev로 병합할 것인가** ← 이번 안건
2. (병합 시) 프론트 기준을 어디로 둘 것인가 — dev 최신 화면 vs integration 블록 13종
3. 각자 개인 브랜치를 병합 후 dev에서 다시 분기할 것인가

---

## 6. 부록 — 함께 정해야 할 계약 (병합 여부와 별개)

| # | 대상 | 내용 |
|---|---|---|
| 1 | 파싱 → 생성 | **챕터 단위** JSON + `source_text` **원문 그대로**(### 소제목·표 보존 필수) |
| 2 | 생성 → 검증 | 문항에 `source_evidence` 동봉 — 원문 대조의 입력 |
| 3 | 전원 | 진도 모델 = **챕터 × 레벨**, 표시는 `맞춘 수 / 전체 문항 수` |
| 4 | 전원 | 레벨 통과 기준 **80%**, 레벨당 목표 문항 수(10~15 제안) |

### 재현 명령

```bash
git rev-list --left-right --count origin/dev...feat/yoonhs-integration
comm -12 <(git diff --name-only $(git merge-base origin/dev feat/yoonhs-integration) origin/dev | sort) \
         <(git diff --name-only $(git merge-base origin/dev feat/yoonhs-integration) feat/yoonhs-integration | sort) | wc -l
```
