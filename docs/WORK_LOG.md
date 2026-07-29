# WORK_LOG (feat/problems · yoonhs 개인 브랜치)

> 개인 작업 로그. **통합/공유 머지에는 포함하지 않는다**(기능 커밋과 분리). 최신 세션이 맨 위.

---

## 세션 02 — 진단 결함 7건 수정·재검증 (2026-07-29)

**사용자 요청**
- `metalearn-problem-gen-task` 메모리의 진단 결함 7건을 우선순위 순서대로 수정.

**한 일 (결함번호 순)**
1. **근거 대조 게이트 강화** — `_evidence_in_source`의 앞 12자 폴백(거짓 주장 통과 구멍) 제거. 근거대조 로직을 `grounding.py`(순수모듈, DB·LLM 비의존)로 분리: 마크다운 장식·표 파이프·불릿·줄바꿈 정규화 후 ①통짜 부분일치 ②실패 시 문장 조각별 원문 실재(SequenceMatcher ≥0.9). **원문 곳곳의 단어를 긁어모은 창작은 조각 단위로 걸러 폐기**. (P-03 close)
2. **개수 준수 + coverage_note 코드 강제** — LLM 자진신고 대신 `service._coverage_note`가 레벨별 요청수 대비 실제수를 세어 미달·폐기 노트를 생성.
3. **에이전트화(자기수정 루프)** — `_generate_for_concept`를 단발 호출→최대 3회(MAX_RETRIES=2) 루프로. 매 시도 검증 통과분 누적, 부족 레벨·직전 폐기 사유를 다음 프롬프트에 피드백 주입, 목표 충족 시 탈출. 중복 문항은 정규화 질문 기준 차단.
4. **solar-pro3 하드코딩 제거** — `settings.SOLAR_MODEL` 신설, `SolarClient`가 settings 기본값 사용 + 호출측 `model=` kwarg override 허용.
5. **표 마크다운 원문 재테스트** — 실제 파싱 출력 형태(표 `| a | b |` + 불릿)의 `payload_table.json`으로 E2E.
6. **L3 지문 어투 규칙** — 프롬프트에 규칙 7 추가("설명하시오/서술하시오" 금지, 모든 레벨 선택형 지문 강제).
7. **잡정리** — 개념 생성 `asyncio.gather` 병렬화 / 로컬 검증 파일 `.gitignore` 등재 / `backend/tests/test_grounding.py` 신설(pytest 없이 `python3`로 실행).

**변경 파일**
- 신규: `backend/app/features/problems/grounding.py`, `backend/tests/test_grounding.py`
- 수정: `backend/app/features/problems/{service,prompts}.py`, `backend/app/core/llm/solar.py`, `backend/app/core/config.py`, `.gitignore`
- (로컬 검증 전용, 커밋 제외): `payload_table.json`

**검증**
- `tests/test_grounding.py` 7/7 통과 — 핵심: 흩어진 단어 조합 창작 근거 폐기(`test_scattered_fabrication_rejected`), 표 셀/불릿 인용 통과.
- E2E(표 마크다운 payload): L1/L2/L3 **각 2문항(총 6) 전부 충족**, 근거 불일치 **4문항 폐기**(coverage_note에 코드가 명시), 전 문항 선택형 어투. 200 OK.

**다음 액션**
- [ ] 세션 01·02 backend 변경 기능 커밋(커밋 여부 사용자 확인 후). WORK_LOG는 분리 docs 커밋.
- [ ] 검증 에이전트 연동 — `grounding.evidence_in_source`를 검증 에이전트 v1이 재사용할지 협의.
- [ ] 문제 유형 확장(규칙채점형), `docs/API.md` 반영.

**열린 이슈 갱신**: P-03 → **closed**(grounding 문장조각 대조로 대체). 나머지 open 유지.

---

## 세션 01 — 문제 생성 에이전트 v1 스캐폴딩·curl 검증 (2026-07-29)

**사용자 요청**
- 메모리(특히 `metalearn-problem-gen-task`)를 읽고 담당 태스크 = 문제 생성 에이전트 구현 착수.
- LLM은 최신 Solar 사용(Solar 3).

**추론·결정**
- 피벗(2026-07-28) 이후 새 베이스는 `dev`. 리모트 정리로 `dev`/`feat/yoonhs-integration`/`main`만 남음 확인 → 태스크대로 `dev`에서 `feat/problems` 분기(worktree `~/metalearn-problems`).
- `dev` 백엔드는 최소 스켈레톤(feature-sliced, sync SQLAlchemy, `core/llm/solar.py`) → 문제생성은 사실상 그린필드. 기존 컨벤션(레이어 주석 [1.Controller]/[2.DTO]/[3.Service]/[5.Entity]) 준수.
- **LLM = Solar 유지**(팀 스택·대회 요건 가능성). Upstage 모델 목록 조회 결과 최신 = `solar-pro3`(`solar-pro3-260323`) 확인 → 스켈레톤의 `solar-pro2`를 `solar-pro3`로 상향.
- **v1 스코프 = mcq(4지선다) L1/L2/L3 우선**. 규칙채점형 확장은 다음.
- **원칙: 원문(source_text)에서만 출제, 외부지식 금지**. 생성물의 `source_evidence`가 검증 에이전트 v1 입력 → 원문 실재 여부를 생성 단계에서 기계 대조(자기검증 아님).
- DB 적재는 검증 통과분만 → v1은 생성·검증(curl)까지, 영속화는 후순위.

**한 일**
- `features/problems/` 신설: `schemas`(입출력 계약, `Level` IntEnum, `answer∈options` 검증) / `prompts`(원문 한정·근거 인용·정답유출 금지 규칙) / `service`(생성 에이전트 오케스트레이션: 프롬프트→Solar(json_object)→방어적 JSON 파싱→문항별 Pydantic 검증→`source_evidence` 원문 실재 게이트→깨진 문항만 폐기, 나머지 보존) / `router`(`POST /generate`).
- `core/llm/solar.py`: 모델 `solar-pro2`→`solar-pro3`, `response_format`/`temperature`/`max_tokens` kwargs 전달 + timeout 120s.
- `api.py`: problems 라우터 `/agents/problems` 등록 → 전체 경로 `POST /api/agents/problems/generate`.

**변경 파일**
- 신규: `backend/app/features/problems/{__init__,schemas,prompts,service,router}.py`
- 수정: `backend/app/core/llm/solar.py`, `backend/app/api.py`
- (로컬 검증 전용, 커밋 제외): `dc.problems.yml`, `_test_curl.sh`, `sample_payload.json`, `backend/.env`(placement에서 복사)

**결과**
- 정보처리기사 "운영체제 - 기억장치 관리" 개념(반입/배치/교체·페이징/세그먼테이션·OPT/FIFO/LRU/LFU) source_text로 L1/L2/L3 각 1문항(총 3) 생성.
- 3문항 전부 검증 통과(폐기 0). 정답=옵션 일치, 오답 보기 맥락 타당, `source_evidence` 전부 원문 그대로 인용. `coverage_note` 빈 값.

**검증**
- `mlprob` 단독 backend 스택(포트 48011, DB 비의존) 기동 → `GET /api/health` 200 → `POST /api/agents/problems/generate` 200, 문항 JSON 확인. `py_compile` 통과.

**다음 액션**
- [ ] backend/app 변경만 기능 커밋(한국어 컨벤션, WORK_LOG는 분리 docs 커밋). 커밋 여부 사용자 확인 후.
- [ ] 문제 유형 확장: 규칙채점형(순서배열·매칭·분류·다중정답·표채우기·수치계산·오류찾기 등) — 유형별 스키마·프롬프트·서버 채점 계약.
- [ ] `docs/API.md`에 엔드포인트 반영.
- [ ] 검증 에이전트 연동 지점 정의(`source_evidence` 대조·정답유출·중복). 진도 에이전트는 추후.
- [ ] 파싱 에이전트에 입력계약(`source_text` 필수·개념 정규화 요구사항) 전달.

### 열린 이슈
| # | 이슈 | 상태 |
|---|---|---|
| P-01 | 레벨별 문항 수·유형 배분 비율 미확정(현재 per_level 상한만) | open |
| P-02 | Solar `response_format` json_object 의존 — json_schema 강제 여부/솔라 지원 재확인 | open |
| P-03 | `source_evidence` 원문 대조가 부분일치(앞 12자) 허용 — 검증 에이전트 본구현 시 정밀화 | open |
| P-04 | DB 영속(문제은행 적재) 미구현 — 검증 통과분 모델/마이그 필요 | open |
