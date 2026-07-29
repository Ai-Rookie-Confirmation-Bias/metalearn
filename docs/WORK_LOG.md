# WORK_LOG (feat/problems · yoonhs 개인 브랜치)

> 개인 작업 로그. **통합/공유 머지에는 포함하지 않는다**(기능 커밋과 분리). 최신 세션이 맨 위.

---

## 세션 03 — 게이트 4·5 신설, 골든셋 벤치, 커밋 정리 (2026-07-29)

**사용자 요청**
- 브랜치 구조 파악 → L3 전멸 버그 수정 → 파이프라인 설계 확정 → 문제 퀄리티 향상(A 커버리지 → C 골든셋) → 커밋·기록.

**추론·결정**
- **파싱 계약을 소제목 단위로 확정**(챕터 통째 아님). 앞서 "챕터만 받고 내가 역산" 안을 냈다가 철회 — `source_text`가 곧 근거 대조 범위이므로, 챕터 전체를 받으면 "페이지 교체" 문항이 "기억장치 관리" 구절을 근거로 붙여도 통과한다. 구간이 좁을수록 대조가 정확하고 커버리지도 균등해진다. 소제목을 못 쪼갠 챕터는 섹션 1개로 보내면 되어 파싱 실패에도 안전.
- **진도 모델 변경**: 개념별 숙련도 %(사진 UI) → **챕터 × 레벨 × "맞춘 수/전체 문항 수"**. 레벨을 축으로 쪼개면 챕터 단위로도 정보량이 충분해져(예: L1 14/15, L2 3/15, L3 🔒) 개념을 잘게 쪼갤 필요가 사라진다. N은 **맞춘 수**(푼 수 아님 — 찍기 방지), 레벨 통과 80%.
- **integration 자산 재활용 방향**(팀 합의 대기). 부품은 그대로 두고 순서만 뒤집는 진화형 — "설명 읽고→문제"를 "문제 풀고→막히면 설명이 열림"으로. 버리는 건 진단 퀴즈·순차 진행 둘뿐. 제안서 1.6("1회성 진단은 스냅샷, 맞춤은 상시 갱신")의 완성형이라 번복이 아니다.
- **품질 로드맵 A→B→C 중 순서를 A→C→B로 변경.** 같은 입력에 결과가 흔들려(문항 15~18, L3 0~3) 측정 수단 없이 B를 하면 개선 여부를 판정할 수 없다.

**한 일**
1. **L3 전멸 버그 수정 (게이트 ③)** — `_segments()`가 정규화 **후** 문자열을 받아 마침표로만 쪼개고 있었다. 한국어 표 셀은 마침표로 끝나지 않아 조각이 1개로 남고, 여러 곳을 인용하는 L3가 전량 폐기됐다(실측 L3 0/2). 정규화 **전** 원본을 받아 **줄·표 셀·문장 경계**로 쪼개도록 변경 → L3 2/2 회생.
2. **서술형 지문 차단 (게이트 ②)** — 프롬프트 규칙 7이 있어도 Solar가 계속 "…비교하여 설명하시오"를 생성. `quality.py` 신설해 코드로 확정 차단(프롬프트는 확률, 코드는 확정).
3. **integration 자산 이식** — `learning/generator.py`를 읽고 IWF(Item-Writing Flaws) 대응을 가져옴: 정답이 개념명에 통째 노출되면 폐기(`_mcq_answer_leaked`), 보기 앞 자체 라벨("A. ") 제거(`_OPTION_LABEL_RE`).
4. **게이트 ④ solve_check 신설** — 기계 게이트 3개를 모두 통과했는데 보기 4개가 전부 정답인 문항이 실측됨("교체 전략의 예시로 제시된 것은? ▶FIFO/OPT/LRU/LFU"). integration의 `verify_cloze_drafts`(Generate-then-Validate) 설계를 mcq로 확장 — 검수 LLM이 출제 정답을 모른 채 직접 풀고, 다른 답을 고르거나 "다른 보기도 정답"이라 하면 폐기. 개념당 배치 1콜, 실패 시 관대 통과(net-additive).
5. **게이트 ⑤ coverage 신설 (A)** — 게이트 ①~④는 전부 *버리는* 장치라, LLM이 표 하나만 파고 나머지를 안 건드려도 잡히지 않았다. `grounding.normalize`를 재사용해 **원문 줄 단위**로 커버 여부를 판정하고, 미커버 줄을 **원문 표기 그대로** 뽑아 재시도 피드백에 주입(측정에서 끝나지 않고 자기수정 루프에 연결). 제목은 분모에서 제외.
6. **골든셋 벤치 (C)** — `bench/golden/os_memory.json`(라벨 15건: pass 6/drop 9, 대부분 실제 생성 출력) + `bench/run_gates.py`. **누락과 과폐기를 함께** 센다(누락은 잘못된 지식을 심고, 과폐기는 문항을 깎고 재시도를 태운다).
7. **팀 제안서 작성** — `docs/PROPOSAL_merge_integration.md`. 브랜치 대조 실측 근거.
8. **커밋 정리** — 미커밋 상태였던 세션 01~03 작업을 의미 단위 8커밋으로 분리.

**도중에 잡은 결함 3건**
- **커버리지 재시도 폭주** — 목표(70%) 미달 시 무제한 재시도로 생성 시간 **23초→140초**(22섹션이면 17분, 업로드 UX 불가). 커버리지만을 이유로 도는 재시도를 1회로 제한 → 27~37초 복구.
- **`coverage_note`가 실제와 다른 값 기록** — 실제 80%인데 49%. 루프 변수의 한 바퀴 전 값을 쓰고 있었다. 최종 문항 목록으로 재계산.
- **검수 게이트가 복수정답을 통과시킴** — E2E에선 사라진 듯 보였으나 골든셋으로 재니 g07이 통과 중. 원인은 검수 LLM이 `also_correct`를 비운 채 `answer`에 나열해 "다 정답"을 표현한 것("FIFO, OPT, LRU, LFU")이고, 약어↔풀네임을 살리려던 포함 관계 비교가 이를 동의로 오판. **검수 답이 보기 2개 이상과 동시에 일치하면 정답 비유일로 폐기**하도록 수정. → **골든셋을 만들자마자 회수한 값**.

**변경 파일**
- 신규: `features/problems/{quality,solve_check,coverage}.py`, `tests/test_{quality,solve_check,coverage}.py`, `bench/golden/os_memory.json`, `bench/run_gates.py`, `docs/PROPOSAL_merge_integration.md`
- 수정: `features/problems/{service,schemas,prompts,grounding}.py`, `tests/test_grounding.py`

**검증**
- 단위 테스트 **36건 통과** (grounding 10 / quality 8 / solve_check 9 / coverage 9).
- 골든셋 **15/15, 누락 0 · 과폐기 0**. 게이트별 폐기 — grounding 4, quality 2, schema 1, solve_check 2.
- E2E(소제목 3섹션 병렬): **18문항**, 서술형 0 · 근거 불일치 0, 커버리지 52~68%, 27~37초.

**커밋** (origin/dev 기준 ahead 8)
`67edb91` gitignore → `12fea80` solar 파라미터·모델 설정화 → `26e6e01` grounding·quality 순수로직 → `0a8b58c` 에이전트 본체 → `f308899` docs → `93426d1` solve_check → `91ca572` coverage → `3abf815` 골든셋 벤치

**다음 액션**
- [ ] **B 레벨 신뢰도**(보류) — 호출 축을 개념×레벨로 분리, L3=서로 다른 근거 2곳 이상 종합으로 기계 검증, 검수에 레벨 적정성 판정 추가.
- [ ] `bench/run_pipeline.py` — 같은 입력 N회 실행해 평균·표준편차 집계. B의 효과 측정에 필요.
- [ ] 파싱 담당에게 계약 전달: **소제목 단위 + `source_text` 원문 그대로**(`###`·표 파이프 보존 필수).
- [ ] 검증 담당과 경계 합의: `grounding`/`solve_check`를 검증 에이전트가 재사용할지.
- [ ] 팀 논의: integration 백엔드 자산의 dev 병합 여부(제안서 참조).

**세션 02 기록 정정**: 위 세션 02의 "문장 조각별 원문 실재(SequenceMatcher ≥0.9)"는 현재 코드와 다르다. `grounding.py`는 **유사도를 쓰지 않고 정규화 후 정확 일치만** 통과시킨다 — "내부 단편화"를 "외부 단편화"로 한 단어만 바꾼 거짓 근거가 유사도 0.98로 통과하기 때문(교육 콘텐츠에서 가장 위험한 오류 유형).

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
| P-03 | `source_evidence` 원문 대조가 부분일치(앞 12자) 허용 — 검증 에이전트 본구현 시 정밀화 | **closed** (세션02 grounding 분리, 세션03 줄·셀 경계 분리로 L3 회생) |
| P-04 | DB 영속(문제은행 적재) 미구현 — 검증 통과분 모델/마이그 필요 | open |
| P-05 | **레벨 오분류** — L3인데 근거 한 줄을 되묻는 L1 수준. 게이트 어디서도 안 잡음. 레벨 게이트·진도 시스템의 근간이라 우선순위 높음 | open (B) |
| P-06 | **생성 편차 미측정** — 같은 입력에 총 문항 15~18, L3 0~3. 단일 실행으로는 개선 판정 불가 | open |
| P-07 | 커버리지 52~68%에서 정체 — 미커버 줄에 약어 풀이("\| **FIFO** \| • First-in First-out")·표 셀 파편처럼 **출제 대상이 아닌 줄**이 분모에 남아 실제보다 낮게 나옴 | open |
| P-08 | 해설(`explanation`) 품질을 아무도 검사하지 않음 — 정확성·충분성 미검증 | open |
| P-09 | 문항 유형이 mcq 단일 — 문제은행이려면 다중정답·O/X·순서배열·매칭 등 필요. 유형마다 정답 타입이 달라 discriminated union 설계 선행 | open |
