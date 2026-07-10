# MetaLearn 작업 일지 (WORK_LOG)

> **Cursor ↔ Claude CLI 공용 일지.** 세션마다 **맨 위에** 새 항목을 append한다.  
> 고정 컨텍스트(제품 철학·아키텍처)는 [`CLAUDE_CONTEXT.md`](./CLAUDE_CONTEXT.md)만 수정한다.

---

## 에이전트 규칙 (Cursor / Claude CLI 공통)

작업 **시작 전** 반드시 읽기:

1. `docs/CLAUDE_CONTEXT.md` — 제품·아키텍처·코딩 원칙
2. `docs/WORK_LOG.md` (이 파일) — **최신 항목 + 열린 이슈 + 다음 액션**

작업 **종료 시** 반드시 기록:

1. 이 파일 **맨 위(구분선 아래)** 에 새 세션 블록 추가 (아래 템플릿 사용)
2. 버그/이슈 상태 변경 시 **열린 이슈** 섹션 갱신
3. 구현 상태가 바뀌면 `CLAUDE_CONTEXT.md` §3 표·§7 표만 짧게 갱신 (일지 본문은 이 파일에만)

### 세션 로그 템플릿

```markdown
## YYYY-MM-DD — [에이전트: Cursor|Claude CLI] — [한 줄 요약]

### 사용자 요청
-

### 추론 / 결정
- 왜 이렇게 했는지

### 한 일
-

### 변경 파일
-

### 결과
-

### 검증
- 실행한 명령·테스트·결과

### 열린 이슈 (이번에 생기거나 남은 것)
- [ ] ...

### 다음 액션
1.
```

---

## 열린 이슈 (스냅샷)

| ID | 우선순위 | 상태 | 내용 |
|----|----------|------|------|
| ISSUE-001 | **P0** | ~~closed~~ | BKT `_params()`: `strength_init` → `p_init` (`diagnostic/service.py:117-118`) — 답안 제출 시 TypeError. **2026-07-02 Claude CLI가 수정, 같은 세션에서 실제 Docker+DB로 E2E 확인 완료(진단 세션 10/10, 크래시 없음).** |
| ISSUE-002 | P1 | ~~closed~~ | `materials→documents` 등 대규모 변경. **2026-07-02 Claude CLI가 커밋(`33a672d`) + `origin/feat/parsing` 푸시 완료.** |
| ISSUE-003 | P1 | ~~closed~~ | migration `0009` 미적용 가능성 우려했으나, **2026-07-02 확인: `alembic current`가 이미 `0009 (head)`** — 실제로는 문제 없었음 |
| ISSUE-004 | P2 | open | `seed` 도메인 스텁 — 씨앗 formalize 미구현 |
| ISSUE-005 | P2 | open | 학습 중 확인 루프 (서버 채점·오답분석·재설명·재생성). **2026-07-09 진전**: 서버 채점 완성(cloze 빈칸별 정오+빈칸별 LLM 폴백, mcq/reveal), 「풀면 진행」게이트(`get_attempted_block_ids` — 오답도 완료 처리, 재설계 §2.2), 정답 공개(학습 블록 정답+해설, 온보딩 퀴즈 last_reveal) — 실 E2E 검증. **남은 것**: LLM 오답 원인 분석(현재 cause는 BKT/DAG 규칙만), 맞춤 재설명 생성(supplement는 같은 블록 재노출뿐), `decide_intervention_stage`(reframe/hint_ladder) 배선(dead code), AI 튜터 채팅 실동작(mock) |
| ISSUE-006 | P3 | open | README `materials` 등 outdated |
| ISSUE-007 | P1 | ~~closed~~ | `learning/service.py` 커리큘럼 모드 분기가 X 자신의 strength만 보고 결정되던 문제. **2026-07-02 Claude CLI가 수정 + 실제 API로 두 분기 모두 재검증 완료.** |
| ISSUE-008 | **P1** | ~~closed~~ | **개념 추출 품질 부족** — course_id=3에서 20개만 추출, 6장 전체 누락. **2026-07-02 Claude CLI가 1단계(섹션 분할+출처+dedup) 구현, course_id=9 재추출 E2E로 검증 완료: 20→1,457개(교재 1,001+AI 보충 456), 6장 포함 전 파트 커버.** 후속: ISSUE-009(granularity), ISSUE-011(잔존 중복·앵커) |
| ISSUE-009 | **P1** | ~~closed~~ | 메인 1,001개 → 진단 폭발 문제. **2026-07-03 조건부 섹션 계층으로 해결, course 12 E2E 완료: 진단 메인 36개, 시작 시 문항 36개만 생성, 오답 시 하위 3개만 샘플 출제(나머지 41개 하향 전파+잠금 유지), 정답 시 하위 31개 자동 확정 — 전 분기 실검증.** 잔여 품질 이슈는 ISSUE-011로 |
| ISSUE-010 | P2 | open | 업로드 동기 HTTP 1건에 ~17분 소요 — ① 임베딩 배치화(현재 개념당 1호출, API는 배열 지원) ② ingest 백그라운드 잡+진행률 폴링 전환. **① 2026-07-04 완료: `embed_batch()`(배열 입력, index 정렬) + `_persist_graph` 전 배치 프리페치(norm당 첫 텍스트, 64개/배치) — resolve는 캐시 미스 시 단건 폴백이라 dedup 정합성 무손실. 미적분 E2E: 132텍스트→3호출, 201/ready. 소형 문서는 추출 LLM이 지배적이라 총시간 개선 미미(66→74s, 실행 편차 포함) — 대형(정처기 ~1,000 embeds)에서 효과 기대, 실측은 다음 정처기 업로드 시. ② 백그라운드 잡은 남음** |
| ISSUE-011 | P3 | ~~closed~~ | 잔존 유사 중복("GROUP BY" vs "[GROUP BY] 절", "Join" vs "JOIN 결과") + 병합 청크 앵커 부정확(첫 섹션 제목이 대표가 되어 "클라우드 서비스"의 앵커가 "■ 트리 순회 방법"). **2026-07-05 해결: 중복은 ① 이름 정규화 강화(공백·대괄호 제거) ② 일괄 dedup 패스(유사도 후보→LLM 배치 판정→병합, 실전 3~4건/코스 병합·오병합 0 확인)로, 앵커는 doc_chunks 영속화 + concepts.source_chunk_id FK로 구조 해결(문자열 anchor는 표시용 유지). 잔여 보수 판정 미병합("INSERT/INSERT 문")은 의도된 편향.** **2026-07-04 원인 실측(0.92 문턱 검증)**: 진짜 중복이 0.75~0.92 구간에 분포("INSERT/INSERT 문" 0.910, "캐시/캐시 메모리" 0.883, "로그함수/로그 함수" 0.756 — 이름+설명 임베딩이라 설명 차이가 유사도를 희석) → **문턱 0.92는 실제 중복을 거의 못 잡음**. 동시에 같은 구간에 별개 개념도 밀집("/24 vs /31 서브넷 마스크" 0.913, "전위 vs 후위 순회" 0.885, "오목 vs 볼록" 0.907) → **문턱을 내리면 오병합** — 단일 유사도 문턱으로는 분리 불가. 개선 후보: ① 이름 정규화 강화(공백·약어 — "일계도함수/일계 도함수"는 규칙으로 해결) ② 후보쌍(sim≥0.85) LLM 동일성 판정 2단계 ③ 이름만 임베딩(소표본에선 분리 개선이나 패러프레이즈 놓침) |
| ISSUE-012 | P2 | open | **수식 부분 평문화** — 2026-07-03 정밀화: 본문 수식 블록은 LaTeX($, \\frac, \\sqrt)로 보존되나, 표/준비학습 등 인라인 수식이 평문화(x²→"x2", eˣ→"ex")되어 개념명에 유입("방정식 ex=4x의 실근 개수"). **260128 vs 260630 파싱 비교 결과 동일**(마커 수 일치) — 버전 문제 아님. 남은 후보: nightly 모드 실험, 추출 프롬프트에서 깨진 수식 정규화 |
| ISSUE-013 | P2 | ~~closed~~ | **elements 청킹에 파트 경계 병합 금지 규칙 없음** — 마크다운 폴백(`chunk_sections`)에는 크로스 파트 선수관계 오염 재발 방지용 "최상위 파트 바뀌면 병합 금지" 규칙이 있으나, 1순위 경로인 `chunk_elements`는 예산(4,000자)만 보고 병합. 파트 전환 지점(예: "소프트웨어 구축" 끝 + "데이터베이스" 첫 섹션)에서 이질 주제가 한 청크로 묶여 ① 엉뚱한 선수관계 에지 ② 섹션 대표 개념 애매화 위험. 실증: course 12 첫 청크가 `"(서문) ~ ▶ 상향식 비용 산정 기법"` — 서문(인사말·목차·저작권)이 본문과 병합돼 LLM에 유입(이번엔 junk 개념 0이었으나 운 의존). 연관: ISSUE-011(병합 앵커 부정확), 정제 단계 설계(2026-07-04 논의: raw_text 보존 + refined_text 2층 구조, 서문류 비학습 콘텐츠 제거가 1순위). **2026-07-04 ISSUE-014 정제 v1의 파트 경계 병합 금지로 해결, E2E 확인.** |
| ISSUE-014 | **P1** | ~~closed~~ | **정제 v1 (2026-07-04 설계 확정)** — 파서 출력 elements를 정제해 새 운영 원본으로. ① `documents.refined_elements` JSONB + `profile` 컬럼(migration 0011) — elements 저장으로 재파싱 없이 재정제 가능 ② 1층 규칙 정제: header/footer/footnote(파서 라벨 + **반복성 교차검증**), 목차·저작권 패턴 — **전부 removed 마킹, 물리 삭제 금지**(오판 시 도장만 떼면 복구) ③ 2층 LLM 스캔 문서당 1회(입력: 헤딩 목록 + 앞 ~40요소 원문): 본문 시작점·파트 경계·프로파일(`linked`/`enumerative`/`mixed`) 판정 — **위치 번호만 반환, 본문 재생성 금지**. 가드레일: 본문 시작점이 수상하면(문서 앞 일정 비율 초과) 판정 기각하고 안 지움. 스캔 결과 JSON도 저장(감사용) ④ 청킹이 refined 사용: removed 스킵 + **파트 경계 병합 금지**(→ ISSUE-013 클로즈). **v1 제외(명시)**: 프로파일 활용(추출 분기·진단 전파·커리큘럼 — 라벨 신뢰도 실측 후 v2), 오탈자 교정, 수식(ISSUE-012 별도), 파트 단위 프로파일. E2E 기준: 정처기+미적분 재업로드 — 서문 유래 청크 소멸 / 프로파일 enumerative·linked / 개념 수 비열화. **2026-07-04 같은 날 구현+E2E 완료(course 19·20): ① 정처기 서문 유래 개념 0(기존 course 12는 4개) ② 프로파일 enumerative/linked 정확 판정 ③ 개념 수 정처기 801→1,011·미적분 110→111(열화 없음, 교재 출처는 597→778로 증가). 잔여: 미적분 표지 캡션 노이즈 2개("무지개") — 보수적 보존의 의도된 비용, v2 후보** |
| ISSUE-015 | **P1** | ~~closed~~ | 진단 재설계 — 온보딩(성향+기반지식)으로 배치고사 대체. **2026-07-09 Claude CLI가 실 DB(mlv2-db)+LLM E2E 완주(course 1d59ab4b): disposition4→probe→quiz→done, 프로필 영속화, 전 절 todo 40섹션·잠금 0, 갭 2 + 선수 에지 역주입 2(에지+외부근거 각 1), 복습 인출 생성 경로(cloze+mcq) 검증.** 배치고사는 lab 동결. |
| ISSUE-018 | **P1** | ~~closed~~ | **책장 진단 상태 오판** — `getCourses.ts`가 `totalSections>0` → `diag_status=completed` 프록시. ingest 후 섹션 생기면 온보딩 전 「완료」 오판. **2026-07-09 Claude CLI 해결: `GET /api/courses`에 `diagStatus`(enrollments.diag_status) 노출 + 프론트가 프록시 대신 소비. 실증: 섹션 10개인 미온보딩 코스가 `not_started`로 정확 분류.** |
| ISSUE-016 | **P1** | ~~closed~~ | **문항 신뢰성 부족** (2026-07-05 사용자 관점 E2E에서 발견, course 24/session 21). ① [심각] mcq 수학 오류 — "y=x³-3x²+1 (2,-3) 접선 기울기" 정답 0이 보기에 없고 "-1"이 정답 마킹. 제대로 계산한 학생이 틀리고 BKT가 오염 ② [심각] 해설에 LLM 자기교정 독백("다시 계산… 문제 오류 가능성…") + 프롬프트 내부 참조("원문 1에서…") 그대로 노출 ③ [중간] 서술 채점 인정 범위 좁음 — 교재 문구("산란")만 정답, 물리적으로 타당한 "분산" 오답 처리 ④ [중간] 표지 지문 유래 노이즈 개념(무지개·물방울) 출제. **원인 분석**: ①②③은 생성 단계 결함(원문 접지는 정상 작동 — 정제 무관), ④만 정제 보수성의 하류 증상(공격적 제거는 본문 손실 위험 → 진단 대상 선정에서 거르는 방안 병행 검토). **대응(착수)**: 해설 정리(프롬프트 규칙+후처리) + 생성 후 문항 검증 패스(mcq 정답 존재·유일·계산 확인, 불합격 재생성). **2026-07-05 구현 완료(`d9f78f3`)**: 원문 근거 주입(출처 청크 발췌 1,500자, 배치는 태그 참조) + 해설 후처리(독백 컷·내부참조 치환·350자) + 검증 패스(검수 LLM my_answer 산출→코드가 대조, 불합격 단건 재생성+1회 재검증). E2E(session 26) 오답 mcq 2건 적발·재생성, 최종 4/4 정확 — ①② 해결로 close. **잔여**: ③ 서술 채점 인정 범위 ④ 노이즈 개념 출제(진단 대상 선정 필터) — 별도 후속 |
| ISSUE-017 | **P1** | open | **씨앗 산출물 계약(docs/ii.md) 대응** — 커리큘럼 팀원이 인수인계 계약 제시(2026-07-05). 이미 일치: 에지 방향(from=학습대상→to=선행), 임베딩 halfvec 4096, depth 방향(기초=큰 값), 절↔대표개념 1:1, mastery=BKT p_known. **신규 작업 4**: ① `concepts.key` 영문 슬러그 생성(코스 내 유니크) ② **`external_refs`** — ai_prereq 개념마다 외부 근거 1행+snippet 필수(없으면 절이 조용히 빔) — 수집 방식 미정(웹 검색 vs LLM 설명 임시) — **최대 과제** ③ chapters/sections 행 생성이 씨앗 소관(파트→chapters, 대표 개념→sections.concept_id, order 10/20/30 간격, gen_status는 pending 유지) ④ enrollments(floor/ceiling/diag_status/purpose)+concept_mastery 초기 시드(locked/todo/mastered) — ISSUE-015 배치고사 출력 스펙으로 확정. **역제안 2**: 키워드 매칭 대신 `concepts.source_chunk_id` FK 조회(개념명↔원문 문자열 불일치 문제 회피), UUID 전환 시점 합의. **DoD**: 커리큘럼 트리 조회→챕터 generate→전 절 blocks 서빙(verified=true)→attempts 채점, 4종 통과 시 인수인계 완료 |

### 다음 액션 (팀 합의 대기 없음 — 우선순위 제안)

1. 학습 중 확인 루프 (ISSUE-005) — 서버 채점·「풀면 진행」·정답 공개 완료, **LLM 재설명 루프** 남음(§2.5)
2. 팀 계약(ii.md, ISSUE-017) — floor/ceiling 의미 축소 합의 + external_refs 후속
3. `redesign/diagnostic-profiling` → dev 머지 (팀 합의 후)

---

## 2026-07-10 — Claude CLI — 성향 진단 → 커리큘럼 반영 검증 (배선 + 라이브 A/B E2E, 코드 변경 없음)

### 사용자 요청
- 전에 구현한 성향 진단이 "설정한 대로" 커리큘럼을 잘 만드는지 테스트. (승인 후) 실 LLM E2E까지 진행.

### 추론 / 결정
- 성향이 커리큘럼에 닿는 유일 경로 = `profile.logic.directive_from_axes` → `learning/service._prepare_generation_input`(§2.3, 첫 생성 맞춤은 성향뿐) → `generator.build_prompt`의 disposition 지시문. 두 층위로 검증: ① 설정→지시문 결정적 변환(DB 무관) ② 실제 LLM 생성물이 성향대로 달라지는가(라이브).
- 라이브는 mlv2 프로젝트(UUID 스키마)가 최신. 처음 뜬 `metalearn` 프로젝트 DB는 구 정수 ID 스키마라 폐기. mlv2 backend가 낡은 네트워크에 붙어 `db` 미해석 → `--force-recreate`로 복구.
- A/B는 `PATCH /profile/me`(manual override → confidence 0.9 즉시 확정)로 성향만 정반대로 놓고 같은 챕터를 두 번 생성해 비교. representation 축은 개수가 아니라 서술 순서/whyItMatters로 반영되므로 블록 개수 대신 whyItMatters 길이·본문 도입부를 지표로.

### 한 일
- 배선 검증 스크립트(scratchpad, `.venv` 실행): 온보딩 신호(`_DISPOSITION_ITEMS`+probe) → `compute_axes` → `directive_from_axes` → `build_prompt` 3시나리오 + 가드 2종 전부 PASS.
- 라이브 A/B: 코스 `66d9048d`(컴윤 v2) 챕터 `4dd07b5c`(3절)를 성향 A(rep/rig/ctx=1.0) → 생성 → 블록 덤프, 성향 B(0.0) → 재생성 → 덤프 후 대조.
- 테스트로 바꾼 상태 원복: dev 프로필 원값(rep 0.9164/rig 0.2891/ctx 0.7953) 복구, 챕터 pending 복귀 + 테스트 생성 블록 24개 삭제.

### 변경 파일
- (제품 코드 변경 없음 — 검증 전용. WORK_LOG만 갱신)

### 결과 / 검증 (실 mlv2 DB + 실제 Solar LLM)
- 배선: 설정값이 결정적으로 지시문으로 변환. 상충 축(rigor 문항 2개 반대 → score 0.5) 중립화, 저신뢰도(conf<0.35) 억제 확인.
- 라이브 A/B(동일 챕터·정반대 성향): whyItMatters 평균 **A 245자 vs B 78자**(3배+, context high="충실히"/low="한 문장"). concept 본문 도입부 — A는 배경·"왜 필요했는지 먼저", B는 정의 직행("~는 …방식이다"). 다루는 개념·범위는 A/B 동일 → 준거 §2.2("설명의 모양만, 내용 범위·분량 불변") 부합.
- 결론: **성향 진단 설정대로 커리큘럼 생성됨**(결정적 변환 + 실 LLM 반영 모두 확인).

### 열린 이슈
- [ ] (관찰) representation 축은 concept 내부 서술 순서/whyItMatters로 반영되지 analogy 블록 개수로는 아님(A/B 모두 절당 analogy 1개). 설계 의도 부합이나, 프론트에서 "성향 반영"을 보이려면 순서/whyItMatters가 관전 포인트.
- [ ] (환경) 로컬에 `metalearn`(구 정수 ID)·`mlv2`(현행 UUID) DB 공존 — 실 검증은 mlv2 프로젝트로.

### 다음 액션
1. 기존 우선순위 유지 — ISSUE-005 재설명 루프 / ISSUE-017 external_refs·dev 머지

---

## 2026-07-09 — Claude CLI — 학습 확인 루프 「풀면 진행」 + cloze 빈칸별 채점 + 온보딩 정답 공개 (컴퓨터 강제종료 중단분 복구·완결)

### 사용자 요청
- 컴퓨터가 꺼져 중단된 미커밋 작업을 이어서 완결 → 실행·E2E → 커밋.

### 추론 / 결정
- 커밋 `4531f31` 이후 미커밋 diff = 재설계 §2.2(「맞혀야 통과」→「풀면 진행」) 학습 확인 루프 구현이 중간에 끊긴 상태. 학습 블록 절반(cloze 빈칸별 채점·게이트·reveal, 프론트 McqBlock/ClozeBlock)은 완성돼 있었고, **온보딩 정답 공개(`last_reveal`)만 백엔드 반쪽** — `OnboardingReveal` 스키마·`OnboardingState.last_reveal` 필드 부재로 **온보딩 answer 호출 시 pydantic 대입 크래시**(끊긴 지점).
- 끊긴 부분만 최소 완결: 스키마/필드 추가 + 프론트 타입 + DiagnosisPage 정답 배너. 나머지는 기존 완성분을 그대로 검증.
- 무관 노이즈(`profile/__init__.py` 개행)는 커밋에서 제외(revert).

### 한 일
- `diagnostic/schemas.py`: `OnboardingReveal`(correct/correct_answer) + `OnboardingState.last_reveal` 필드
- `frontend/diagnostic/types.ts`: `OnboardingReveal` + `last_reveal`; `DiagnosisPage.tsx`: quiz 단계 직전 문항 정답 배너
- (기존 완성분 유지) `verify_grade.py` `cloze_parts`/`grade_cloze_blanks`, `grading.py` 빈칸별 LLM 폴백, `repository.get_attempted_block_ids`, `service.record_attempt` 「시도=완료」 게이트 + `_build_reveal(blank_results/hint)`, McqBlock/ClozeBlock 「첫 확인=확정+정답·해설 노출」, LearningPage 몰입 뷰어 토글

### 변경 파일
- backend: `core/verify_grade.py`, `features/diagnostic/{onboarding,schemas}.py`, `features/learning/{grading,repository,schemas,service}.py`
- frontend: `features/diagnostic/types.ts`, `features/learning/blocks/{ClozeBlock,McqBlock,types}.tsx?`, `pages/{DiagnosisPage,LearningPage}.tsx`

### 결과 / 검증 (실 Docker+DB+LLM, project `mlv2`, head 0019)
- 온보딩 E2E(course bdf5d247): disposition4→probe→quiz3→done, **quiz 답변마다 `last_reveal`(correct+correct_answer) + 완료 응답에도** — 수정 전이라면 첫 quiz에서 크래시. 프로필 label/seeded=10/gaps=2/injected=2
- 학습 attempt(course 66d9048d): cloze 오답 → `blankResults=[False]` + 실제 정답 공개 + 힌트(148자); mcq 오답 → `answerIndex`+해설(248자)
- 「풀면 진행」 게이트: 완료 이력 **없던** 섹션 `dd3bdf4d`를 tracked 3블록 **전부 오답** 시도 → `section_progress=completed`(구 게이트라면 미완료). 백엔드 로그 예외 0
- 백엔드 import·`grade_block` 3경로(빠른/폴백/오답) 스텁 LLM 통과. 프론트 tsc는 환경(pnpm 미설치)상 스킵 — 타입 정합 수동 확인

### 열린 이슈
- [ ] ISSUE-005 남은 절반: LLM 오답 원인 분석 + 맞춤 재설명 생성 + `decide_intervention_stage` 배선 + AI 튜터 채팅 실동작
- [ ] ISSUE-017 external_refs / dev 머지(팀 합의)

### 다음 액션
1. ISSUE-005 재설명 루프 — #2(맞춤 재설명 생성, generator 재활용) 우선 권장
2. 팀 합의 후 dev 머지

---

## 2026-07-09 — Claude CLI — 온보딩 재설계 검증(Composer 접합) + E2E + ISSUE-018 + 커밋

### 사용자 요청
- 핸드오프(위 세션)와 `DIAGNOSTIC_REDESIGN_BRIEF.md` 읽고 동기화. Cursor가 페이블→Composer 모델로 갈아타며 만든 접합부가 이상하게 구현됐는지(Composer가 페이블보다 약해 오해 가능성) 검증.
- E2E 돌려 이상 없으면 나머지(ISSUE-018·QuizPanel·커밋·문서)까지 처리.

### 추론 / 결정
- **Composer 접합 정적 리뷰**: generator(성향 지시문·복습 인출), learning.service(첫 생성 strength 제거→성향만, 복습 섹션 주입), repository(오답노트·SM-2 병합·복습 섹션), seed(finalize_onboarding), 프론트 전부 정독. 준거(§2.2 내용 안 깎음, §2.3 첫 생성=성향)와 정합. 우려한 지점 모두 무해 확인: `fake_section` 핵은 `_prepare_generation_input`이 concept_id만 읽어 안전 / `seed_mastery_if_absent`가 온보딩 BKT strength 보존(locked 행만 승격) / `_first_prerequisite`는 `str(id)` 정규화로 타입 안전.
- **DB 드리프트 발견·해소**: `metalearn-db` 볼륨은 정수 PK(UUID 전환 이전)라 현재 코드와 호환 불가 — 폐기. 실 활성 스택은 `mlv2-*`(이 repo backend 마운트, courses.id=uuid). mlv2-db가 0016에 머물러 0018·0019 미적용 → `alembic upgrade head`로 적용.
- ISSUE-018은 프록시(`totalSections>0`)를 서버 진실(`enrollments.diag_status`)로 교체.

### 한 일
- 온보딩 E2E(실 HTTP, mlv2-backend, course 1d59ab4b): disposition4→probe→quiz(mcq3)→done. 프로필 축·라벨 산출·영속(GET /me 일치), 전 절 todo 40섹션·커리큘럼 잠금 0(injected 2만 locked), 갭 2 + 선수 에지 역주입 2(각 에지1+외부근거1), enrollment.diag_status=completed.
- 복습 인출 경로 E2E: `collect_review_concepts`([] 정상) + `generate_retrieval_blocks`(cloze+mcq verified, kind=review, 성향 지시문 주입).
- ISSUE-018: `curriculum/repository.diag_status_by_course` + `CourseListItem.diag_status` + router 배선 + `getCourses.ts`가 `diagStatus` 소비. API 실검증(섹션10 미온보딩 코스=not_started).
- QuizPanel `key={question.id}` — 문항 전환 시 입력 잔존 제거.
- `CLAUDE_CONTEXT.md` §3·§7 온보딩/복습/프로파일 반영, migration head=0019.

### 변경 파일
- `backend/app/features/curriculum/{repository,router,schemas}.py`
- `frontend/src/features/library/api/getCourses.ts`, `frontend/src/pages/DiagnosisPage.tsx`
- `docs/CLAUDE_CONTEXT.md`, `docs/WORK_LOG.md`
- (기존 미커밋 온보딩 세트 포함 커밋)

### 결과
- 온보딩·복습 양 경로 실 DB+LLM E2E 통과. Composer 접합 기능 결함 없음(정적+실행 확인).
- migration 0018·0019 mlv2-db 적용 완료(head).

### 검증
- `uv run python` 전 모듈 import + profile logic 실행. 온보딩/복습 E2E(컨테이너 실행). `GET /api/courses` diagStatus 실응답. 프론트 `tsc --noEmit` 무오류.

### 열린 이슈
- [ ] ISSUE-005 학습 중 확인 루프(복습 섹션 주입은 착수)
- [ ] 팀 계약(ii.md, ISSUE-017): floor/ceiling 의미 축소 합의 + external_refs 후속
- [ ] `redesign/diagnostic-profiling` → dev 머지(팀 합의 후)

### 다음 액션
1. 학습 중 인출→오답노트→다음 장 복습 소비 전 구간 실사용 E2E(학습 attempt 있는 상태)
2. 팀 계약 합의 후 dev 머지

---

## 2026-07-09 — Claude CLI 핸드오프 — 진단 재설계(온보딩) 전체 기록

> **브랜치**: `redesign/diagnostic-profiling` (dev 머지 금지)  
> **준거 문서**: `docs/DIAGNOSTIC_REDESIGN_BRIEF.md`, 제안서 `docs/DIAGNOSTIC_REDESIGN_PROPOSAL.md`  
> **에이전트 이력**: Cursor 페이블(제안서·골격) → Cursor Composer(접합·프론트) — **코드 충돌 없음, 커밋 전**

### 배경 — 무엇을 바꿨나
진단 목적을 **「수준(floor) 찾기」→「학습 성향 프로파일링 + 기반지식 체크」** 로 교체.
- **내용을 수준으로 깎지 않음** — 전 절 todo, locked/mastered 위치 시딩 폐기
- **첫 생성 맞춤 = 성향만** — strength 기반 난이도는 복습/보충으로 이관
- **수준 반영 = 복습 국면** — SM-2 due + attempts 오답노트 → 다음 장 맨 앞 복습 섹션

### 설계 결정 요약 (제안서 §e)
| 항목 | 결정 |
|---|---|
| 성향축 | 연속 3축 `representation` / `rigor` / `context` + confidence (유형 라벨은 표시용만) |
| 성향 저장 | `learner_profiles` (user 단위, migration **0019**) |
| 성향 측정 | 고정 상황판단 4문항 + 스타일 프로브 1 + (후속) 학습 행동 EMA |
| 기반지식 | 첫 파트 대표에서 선수 사슬 최대 2단 하강 → **갭 목록** (floor 아님) |
| 복습 시점 | SM-2 `next_due_at` + 챕터 생성 시 맨 앞 섹션 주입 |
| 망각곡선 | SM-2 (기존 `review/sm2.py`) |
| 오답노트 | 별도 테이블 없음 — `attempts` 파생 (`get_wrong_note_concepts`) |

### 구현 완료 (실사용 경로)

**온보딩 진단** (`backend/app/features/diagnostic/onboarding.py`)
- 3단계: `disposition`(4문항) → `probe`(비유 vs 원리 LLM) → `quiz`(기반지식, 하강 재활용)
- 종료: 프로필 upsert + `finalize_onboarding` + (상한 2) 선수 에지 역주입
- API: `POST /api/diagnostic/onboarding/start`, `POST /api/diagnostic/onboarding/{id}/answer`

**성향 프로파일** (`backend/app/features/profile/`)
- `logic.py`: EMA, `directive_from_axes`, `profile_label`
- API: `GET/PATCH /api/profile/me`

**시딩** (`seed/service.py::finalize_onboarding`)
- 진행선 **전 절 todo** — `classify_placement` 미사용
- `enrollment.self_report.foundation`에 갭·probed 기록
- floor/ceiling 컬럼은 참고 표식만 (팀 계약 충돌 — 합의 필요)

**생성·복습** (`learning/`)
- `generator.build_prompt`: `disposition_directive` 주입, strength 난이도 제거(표준 2)
- `generate_retrieval_blocks`: 복습 전용 cloze/mcq
- `run_chapter_generation`: SM-2 due + 오답노트 → 「복습 · 오답 체크」섹션(order_index=0)
- `initialize_placement`: `self_report.foundation` 있으면 온보딩 경로(전 todo), 없으면 구 배치고사(lab)

**프론트**
- `DiagnosisPage.tsx`: 온보딩 3단계 UI + 종료 프로필 카드 (`initPlacement` 호출 **제거**)
- `onboardingApi.ts`, `types.ts` 온보딩 DTO
- `SettingsPage.tsx`: 3축 슬라이더

**lab 동결**: `/api/diagnostic/placement/*`, 구 전수 `/start` — 그대로 유지

### 변경 파일 (미커밋 — `git status` 기준)
```
M  backend/alembic/env.py
M  backend/app/api.py
M  backend/app/features/diagnostic/router.py
M  backend/app/features/diagnostic/schemas.py
M  backend/app/features/learning/generator.py
M  backend/app/features/learning/repository.py
M  backend/app/features/learning/service.py
M  backend/app/features/seed/service.py
M  frontend/src/features/diagnostic/types.ts
M  frontend/src/pages/DiagnosisPage.tsx
M  frontend/src/pages/SettingsPage.tsx
?? backend/alembic/versions/0019_learner_profiles.py
?? backend/app/features/diagnostic/onboarding.py
?? backend/app/features/profile/
?? backend/tests/test_profile_logic.py
?? frontend/src/features/diagnostic/api/onboardingApi.ts
?? docs/DIAGNOSTIC_REDESIGN_PROPOSAL.md  (제안서, docs/ 미추적일 수 있음)
```

### 검증된 것 / 안 된 것
- ✅ `uv run python` import OK (profile, onboarding, learning.service)
- ✅ profile logic 인라인 assertion 5케이스
- ❌ Docker E2E (온보딩→장 생성→복습 섹션)
- ❌ `alembic upgrade head` (0019) — **Claude 시작 시 먼저 적용**
- ❌ git commit / push
- ❌ `CLAUDE_CONTEXT.md` §3·§7 표 갱신 (여전히 「배치고사」표기)

### 알려진 버그·갭 (Claude 우선 처리 후보)
1. **ISSUE-018 (신규)** 책장 `diagStatus` 프록시: `getCourses.ts`가 `totalSections > 0`이면 진단 완료로 간주 → 업로드 직후 `build_tree`로 섹션이 생기면 **온보딩 건너뛰고 `/learning`으로 갈 수 있음**. `enrollments.diag_status`를 API에 내려주고 프론트가 그걸 쓰게 고칠 것.
2. **CreateCoursePage `?purpose=`** — URL에 purpose를 넘기지만 DiagnosisPage/온보딩이 읽지 않음 (구 배치고사도 동일 — 선행 과제).
3. **팀 계약(ii.md)**: floor/ceiling·mastered/locked 시딩 의미 변경 — 팀 합의 전 브랜치 한정.
4. 레거시 파일 `placementApi.ts`, `completionApi.ts` — 실사용 경로에선 미사용, 정리는 선택.

### Claude CLI 시작 프롬프트 (복붙용)
```
docs/WORK_LOG.md 맨 위 「2026-07-09 — Claude CLI 핸드오프」와
docs/DIAGNOSTIC_REDESIGN_BRIEF.md 를 읽고 동기화해.
브랜치 redesign/diagnostic-profiling, 미커밋 상태 확인.
다음 액션 순서:
1) docker compose up + alembic upgrade head (0019)
2) 온보딩 E2E (업로드→/diagnosis/:id→프로필 카드→책장)
3) ISSUE-018 책장 diag_status 연동
4) 통과하면 커밋 + CLAUDE_CONTEXT §3·§7 갱신
```

### 다음 액션 (Claude CLI)
1. `alembic upgrade head` + Docker 온보딩 E2E
2. ISSUE-018: `GET /api/courses`에 `diag_status` 추가 + `LibraryPage`/`getCourses.ts` 수정
3. 커밋 (메시지: 진단 재설계 — 온보딩·성향·복습 루프)
4. `CLAUDE_CONTEXT.md` §3·§7 — 「배치고사」→「온보딩 진단」으로 갱신
5. ISSUE-015 상태를 open→in_progress 또는 superseded by onboarding 으로 정리

---

## 2026-07-09 — Cursor — 진단 재설계 구현 (온보딩 + 성향 + 복습 루프)

### 사용자 요청
- 제안서 승인에 따라 `redesign/diagnostic-profiling` 브랜치에서 전체 구현. 사용자 입장 최적 UX 포함.

### 추론 / 결정
- 기존 부분 구현(profile/onboarding/finalize_onboarding/migration)을 기반으로 **남은 접합부** 완성:
  - `generator`: 성향 지시문 + `generate_retrieval_blocks`(복습 전용 인출)
  - `learning/service`: 첫 생성 strength 난이도 제거 → profile directive 주입; `run_chapter_generation`에 SM-2 due+오답노트 복습 섹션 맨 앞 주입; `initialize_placement`는 `self_report.foundation` 있으면 전 절 todo(온보딩 경로) — classify_placement 우회
  - `repository`: `collect_review_concepts`, `get_wrong_note_concepts`, `get_or_create_review_section`; BlockDraft에 concept_id/kind per-block
  - 프론트: DiagnosisPage → 3단계 온보딩 UI + 종료 프로필 카드; SettingsPage → 3축 슬라이더; initPlacement 호출 제거(서버 finalize_onboarding가 시딩 완료)

### 한 일
- 백엔드: profile 도메인, onboarding 서비스, finalize_onboarding, migration 0019, API `/onboarding/*` + `/profile/me` (기존) + learning 복습/생성 주입 (신규/보완)
- 프론트: `onboardingApi.ts`, `DiagnosisPage.tsx` 전면 교체, `SettingsPage.tsx` 성향 슬라이더, `types.ts` 온보딩 DTO
- 테스트: `backend/tests/test_profile_logic.py` 5케이스 통과

### 변경 파일
- `backend/app/features/profile/*`, `diagnostic/onboarding.py`, `diagnostic/router.py`, `diagnostic/schemas.py`
- `backend/app/features/seed/service.py`, `learning/generator.py`, `learning/service.py`, `learning/repository.py`
- `backend/alembic/versions/0019_learner_profiles.py`, `backend/alembic/env.py`, `backend/app/api.py`
- `frontend/src/pages/DiagnosisPage.tsx`, `SettingsPage.tsx`, `features/diagnostic/api/onboardingApi.ts`, `types.ts`
- `backend/tests/test_profile_logic.py`

### 결과
- 실사용 진단 경로 = 온보딩(성향→프로브→기반체크). 배치고사 `/placement/*`는 lab 동결.
- Docker E2E 미실행(로컬 import·pytest만). `pnpm` 미설치로 프론트 tsc 스킵.

### 검증
- `uv run python -c "…imports…"` OK
- profile logic 인라인 assertion 5케이스 OK (pytest 미설치)

### 열린 이슈
- [ ] Docker+DB E2E: 온보딩→장 생성→인출→다음 장 복습 섹션 주입 전 구간
- [ ] 팀 계약(ii.md): floor/ceiling 의미 축소 — 팀 합의
- [ ] `alembic upgrade head` (0019) 운영 DB 적용

### 다음 액션
1. Docker E2E로 온보딩+챕터 생성 실측
2. CLAUDE_CONTEXT §3·§7 표 갱신(진단=온보딩)

---

## 2026-07-09 — Cursor — 진단 재설계 제안서 작성 (성향 프로파일링 + 기반지식 체크) — 승인 대기

### 사용자 요청
- `docs/DIAGNOSTIC_REDESIGN_BRIEF.md` 준거로 진단의 목적을 "floor 찾기" → "성향 프로파일링 + 기반지식 체크"로 교체하는 재설계. 코드 수정 전에 제안서((a)~(g)) 먼저 — 승인 후 구현. 브랜치 `redesign/diagnostic-profiling` 한정.

### 추론 / 결정 (제안서 핵심 — 상세는 `docs/DIAGNOSTIC_REDESIGN_PROPOSAL.md`)
- 준거 위배의 본체는 배치고사 자체가 아니라 `learning/mastery.py::classify_placement()`의 위치 시딩(floor 아래=mastered 건너뜀, ceiling 위=locked)임을 코드로 확인 → 이것을 버리고 전 절 todo 시딩으로 교체
- 성향축: 유형 라벨 대신 **연속 3축**(representation/rigor/context) + confidence, 사용자 단위 신규 테이블 `learner_profiles` 1개(이번 재설계의 유일한 신규 테이블). 측정 = 고정 상황판단 4문항 + 실교재 스타일 프로브 1 + 학습 중 행동 신호 EMA
- 성향→생성: 축 임계값 → **결정적 지시문 조각**을 `generator.build_prompt`에 주입 (LLM에 해석 위임 금지 — 검증 가능성). 성향은 모양만 바꾸고 양은 못 건드림(§2.2 가드)
- 기반지식 체크: 기존 하강 엔진 재활용하되 방향 역전 — 천장에서 바닥 찾기가 아니라 **첫 파트 입구에서 밑바탕 파기**(최대 2단), 산출물 = 갭 목록 → 기존 prerequisite 삽입 기제에 mastery 신호로 꽂음 + 에지 역주입(상한 2)
- 비어있던 기준 결정: 망각곡선=**SM-2**(이미 구현·컬럼 존재, HLR은 데이터 축적 후 교체 후보), 복습 소비 시점=**다음 장 맨 앞 복습 섹션**(`run_chapter_generation` 접합), 수준 척도=strength 3구간(안다≥0.8&2연속정답/약점<0.4∨2연속오답/학습중 — 오답노트·복습 우선순위에만 사용), 오답노트=**새 테이블 없이 attempts 파생**(append-only라 누적 공짜)
- 준거 이탈 기록: 브리프 §3-1 "진단 딱 한 번" 대비, 성향 *프로파일*은 학습 중 행동 신호로 계속 정련하기로 함 — 진단 이벤트는 한 번이고 측정은 인출/행동 데이터 재활용이므로 준거 6·8번 정신과 일치한다고 판단
- 첫 생성의 strength 기반 difficulty_hint 제거 결정 (§2.3 "첫 생성 맞춤은 성향만" 위배 지점)

### 한 일
- 브리프 + CLAUDE_CONTEXT + WORK_LOG 동기화, 지정 4파일 + `mastery.py`/`generator.py`/`next_action.py`/`sm2.py`/`learning/service.py`/curriculum 모델 실코드 확인
- `docs/DIAGNOSTIC_REDESIGN_PROPOSAL.md` 신규 작성 — (a)버릴것/살릴것 (b)성향 모델·측정 (c)기반 체크 (d)오답노트 루프 접합 (e)비어있던 기준 결정·근거 (f)스키마 영향(additive only, 신규 migration 1개) (g)7단계 구현 순서

### 변경 파일
- `docs/DIAGNOSTIC_REDESIGN_PROPOSAL.md` (신규), `docs/WORK_LOG.md` (이 로그)

### 결과
- 제안서 승인 대기. 코드 변경 없음.

### 검증
- 해당 없음 (설계 세션)

### 열린 이슈 (이번에 생기거나 남은 것)
- [ ] 팀 계약(ii.md/ISSUE-017) 충돌: floor/ceiling·mastered/locked 시딩 의미 변경 — 팀 합의 전 브랜치 한정
- [ ] 성향 고정 문항 문구 확정 (구현 시 초안 → 사용자 다듬기)

### 다음 액션
1. 사용자 제안서 승인/수정 → 승인 시 제안서 §7 순서로 구현 착수 (1: learner_profiles 계층부터)

---

## 2026-07-06 — Claude CLI — WORK_LOG 유실 발견·복원 (히스토리 재작성 부수효과)

### 사용자 요청
- 진행 상황 브리핑 → "WORK_LOG가 커밋보다 뒤처졌다"는 내 분석에 사용자가 반박(히스토리 재작성 의심) → 조사 → 복원 + ISSUE-016/017 세션 로그 보충 지시

### 추론 / 결정
- 처음엔 "7-04~7-05 세션들이 일지를 안 남겼다"고 오판. 사용자 지적으로 재조사:
  - 로컬 WORK_LOG는 759줄, 최신 세션이 7-03에서 멈춤
  - `git log --all -- docs/WORK_LOG.md`에 재작성 전 옛 커밋들(`90e1f7f`=구 ISSUE-017 커밋 등)이 잔존, `90e1f7f` 시점 WORK_LOG는 866줄로 7-04·7-05 세션 2개 + ISSUE-013~017 이슈표까지 완비
  - 결론: **기록 누락이 아니라, 7-05 docs/ 원격 제거 히스토리 재작성(`99d43de`, .gitignore `docs/`) 때 로컬 파일이 옛 버전으로 되돌아간 것**

### 한 일
- `git show 90e1f7f:docs/WORK_LOG.md`로 전문 복원 (759→866줄, 유실됐던 7-04 "정제 v1 설계 확정"·7-05 "실사용 테스트+진단 재설계" 세션 및 이슈표 013~017 회수)
- ISSUE-016/017 구현 세션 로그 소급 작성 (바로 아래 2026-07-05 항목 — 커밋 `867870d`·`d9f78f3`·`d3217a8` 기준)
- 이슈표 갱신: ISSUE-016 closed(잔여 ③④ 명시), ISSUE-017에 ①③④ 구현 기록(② external_refs 남아 open 유지)

### 주의 (기록 유실 재발 방지)
- docs/는 이제 **git 미추적** — 복원의 근거였던 옛 커밋들은 dangling 상태라 GC되면 소실됨. 이후 일지 백업은 OneDrive 동기화에만 의존
- 히스토리 재작성·브랜치 강제 체크아웃 후에는 docs/ 파일이 덮이지 않았는지 확인할 것

### 다음 액션
1. CLAUDE_CONTEXT §3·§7 표를 ISSUE-016/017 반영해 갱신 (미실시 — 사용자 지시 대기)
2. 위 "다음 액션 (팀 합의 대기 없음)" 섹션이 ISSUE-008(closed) 기준으로 구식 — 갱신 필요

---

## 2026-07-05 — Claude CLI — ISSUE-016 구현 완료 + ISSUE-017 ①③④ 구현 + 정제 가드레일 (소급 작성)

> **소급 기록** (2026-07-06 작성): 이 세션의 종료 로그는 히스토리 재작성 직전이라 원래 없었음. 커밋 `867870d`·`d9f78f3`·`d3217a8`·`99d43de`(전부 07-05 17:37~21:31) 메시지·diff 기준으로 재구성.

### 한 일

**① 정제 스캔 보강 (`867870d`)** — 가드레일 3종 + 통계 주입 (LLM 스캔 판정 변동성 대응)
- `documents/refinement.py` +58/-16, `documents/service.py` 1줄

**② ISSUE-016: 진단 문항 원문 근거 주입 + 검증 패스 (`d9f78f3`)**
- 원문 주입(RAG 1호): `repo.get_chunk_contents()` 신설 + 문항 프롬프트에 출처 청크 발췌(1,500자 상한). 배치는 같은 청크 공유 개념이 많아 원문 1회 게재 + `(원문 N)` 태그 참조로 중복 방지
- 해설 정리: 프롬프트 규칙(1~2문장, 자기교정·내부참조 금지) + 후처리 `_clean_explanation()`(독백 마커 5종 컷, "원문 N"→"교재" 치환, 350자 상한) — session 21 실측 독백 노출 차단
- 문항 검증 패스: 검수 LLM은 `my_answer`만 산출하고 mcq 정답 대조는 코드가 수행(정규화+포함 매칭 `_answers_match`) — 검수자가 옳게 계산하고도 비교에서 오판하던 실측 한계 우회. 불합격은 단건 재생성 + 재생성분 1회 재검증(2회째 불합격은 로그 남기고 사용 — 무한 루프 방지). 검증 호출 실패는 비치명(생략)
- 배치 생성 재시도를 ValueError(JSON 절단)까지 확장 (실측 500 대응)

**③ ISSUE-017: 씨앗 산출물 계약 — 신규 작업 4 중 ①③④ 구현 (`d3217a8`)**
- migration `0013_seed_contract`: chapters/sections 테이블 + `concepts.key` + enrollments(floor/ceiling/floor_found/purpose)
- `seed/service.py` 신규 234줄 (ISSUE-004 스텁 실구현): `POST /api/seed/{id}/build`
  - 커리큘럼 트리: 정제 스캔 파트→chapters(order 10/20/30, gen_status pending 고정), 섹션 대표 개념→sections.concept_id 1:1 (계약 규약)
  - key 슬러그: LLM 배치 생성(80개/배치) + 코스 내 유니크화 + 폴백(`concept-{id}`)
  - enrollment 확정 + mastery 초기값(mastered/todo/locked+strength) 시드 JSON — 진단 신호 최다 세션 채택(미응답 세션 누적 결함 실측 후). `concept_mastery` 테이블 기록은 UUID 이관 시점으로 유보
- **② external_refs는 미착수** (최대 과제 — 수집 방식 미정: 웹 검색 vs LLM 임시)

**④ docs/ git 추적 제외 + 히스토리 재작성 (`99d43de`)** — 로컬 작업 문서 원격 미공유. 부수효과: 로컬 WORK_LOG가 옛 버전으로 덮여 7-04~7-05 기록 일시 유실 (7-06 복원됨, 위 항목)

### 변경 파일
- `backend/app/features/documents/refinement.py`, `documents/service.py` (가드레일)
- `backend/app/features/diagnostic/repository.py`, `diagnostic/service.py` (ISSUE-016)
- `backend/alembic/versions/0013_seed_contract.py`, `features/seed/{router,service}.py`, `documents/models.py`, `diagnostic/models.py` (ISSUE-017)
- `.gitignore` (docs/ 제외)

### 검증
- ISSUE-016 E2E(session 26): 검증 패스가 오답 mcq 2건 적발·재생성, 최종 mcq 4/4 수학 정확
- ISSUE-017 E2E(course 24): 챕터 8·절 28 생성, 슬러그 152개(LLM 140), floor=오답 개념 확인

### 열린 이슈
- [ ] ISSUE-017 ② external_refs — ai_prereq 개념별 외부 근거+snippet (없으면 절이 조용히 빔)
- [ ] ISSUE-016 잔여: ③ 서술 채점 인정 범위 좁음 ④ 노이즈 개념(표지 캡션) 출제 — 진단 대상 선정 필터 검토

---

## 2026-07-05 — Claude CLI — 실사용 테스트 + 팀 스키마 검토 + 진단 재설계 결정(ISSUE-015)

### 사용자 요청
- 프론트(localhost:5173) 실사용 테스트 (정처기 업로드, 진단·문제 풀이 체험)
- 팀원 스키마(docs/schema.md) 검토 + 팀 공유 코멘트 문서화
- 진단 문항 과다 체감 → 진단 재설계 방향 논의·기록

### 한 일
- **실사용 E2E (doc/course 23)**: 201/ready, 개념 897개(교재 614+보충 283), **총 ~4분** (동일 문서 이틀 전 13.5분 → 임베딩 배치 903텍스트/15호출 실측, ISSUE-010 ① 대형 검증 완료). 추출 재시도 안전망 1회 작동(재시도 성공 66타겟)
- **dedup 패스 첫 실전 병합**: 후보 9쌍 → LLM 판정 3쌍 병합. 생존 6쌍 검수 — 순회 3형제·해시함수/해시값·데이터/논리적 독립성 모두 옳게 보존. "INSERT/INSERT 문"(0.855)은 보수 판정으로 미병합(의도된 편향의 비용)
- **팀 스키마 검토** → `docs/schema_feedback.md` 작성: 임베딩 Solar 확정(1536→halfvec 4096 수정 필요), doc_chunks 드릴다운 주소 컬럼 제안, 정제 산출물 자리(refined_elements/profile) 제안, concepts 임베딩+출처 링크 제안, contains 에지↔chapters/sections 이관 매핑, 질문 3건
- **ISSUE-015 기록**: 진단 재설계 (배치고사식 축소 + 학습 중 정밀화 이관, ISSUE-005와 통합 설계)

### 관찰 (미해결)
- **스캔 변동성 3차 확인**: course 23에서 파트 1개·프로파일 mixed (course 19: 파트 12개·enumerative) — 이번 런은 파트 경계 보호 사실상 미작동. 프롬프트 보강+가드레일 수정안 제안됨, 승인 대기
- **추출 변동성**: 동일 문서 교재 개념 597→778→614, 저품질 청크(타겟 5개) 2건 간헐
- 병합 쌍 이름 로깅 부재(건수만 기록) — 감사성 개선 후보

### 추가 (같은 날): 팀 스키마 정렬 — doc_chunks 영속화 + 시드 초안
- **migration 0012**: `doc_chunks` 테이블(element_from/to·heading·part_index·page·halfvec 4096) + `concepts.source_chunk_id` FK — schema_feedback §2·4의 lab 선반영
- ingest가 청크를 영속화(청크 임베딩 배치 포함, RAG 검색 계층) → 개념 저장 시 chunk FK 기록 → **ISSUE-011 클로즈** (중복=정규화+dedup 패스, 앵커=chunk FK)
- **E2E (미적분, 201/90.5s)**: doc_chunks 10행 전부 요소 좌표·페이지·임베딩 채워짐, 교재 개념 96/96 chunk FK 연결, 개념→청크 원문 조인 확인. dedup 4건 병합. 서문 오판 없음(front_matter 1)
- `docs/schema_feedback.md` 갱신: 1~4 lab 반영 상태, 5 결정(contains→팀 스키마 따름, 이관 시 chapters/sections 변환), §6 역할 경계 제안(청크 생성=데이터 파트/verified 검증기 제공/storage_url nullable), §7 섹션↔대표 개념 연결 권고
- `docs/seed_spec_draft.md` 신규: 배치고사식 흐름 + 시드 페이로드 초안(가벼운 수준 추정+근거, 깊은 판정은 커리큘럼 파트) + 합의 필요 4건
- 스캔 변동성 4차: 미적분 프로파일 linked 2회 vs enumerative 2회, 파트 4→8개 — 보강 수정 근거 누적

### 추가 (같은 날): 스캔 보강 (사용자 승인 후 수정)
- 프롬프트: 비학습 콘텐츠 정의 한정(표지·인사말·목차·저작권·구매안내만, "준비 학습·연습 문제·수식·표는 본문" 명시) + 문서 통계(수식/표/문단/헤딩 수) 주입 + 파트는 목차 대조·소제목 금지
- 가드레일 3종 (`_sanitize_scan`): ① 서문 구간에 table/equation/chart 있으면 기각 ② parts 20개 초과 기각(실측: 단일 단원에 57개 오판) ③ 기존 비율 상한. 기각 = 아무것도 안 지움
- dedup 병합 쌍 이름 로깅 추가 (감사성)
- 검증: 과거 오판 문서(doc 22) 재스캔 2회 — **body_start=3 안정, 준비학습 보존** (이전 오판: 13까지 삭제, 교재 개념 80→49). 정처기 body_start=14 안정. 가드레일 단위 검증 4케이스 통과
- **잔여 (미해결)**: parts·profile 판정의 실행 간 편차는 여전 (정처기 profile enumerative↔linked, parts 1↔12). 내용 손실 위험은 가드레일로 차단됐고 profile은 v1 미사용이라 무해 — v2에서 profile을 규칙 기반(수식 비율 등) + LLM 타이브레이크로 바꾸는 것 검토

### 추가 (같은 날): 문항 생성 원문 근거 주입 — doc_chunks 첫 소비자 (RAG 1호)
- `DiagnosticRepository.get_chunk_contents()` + `_quiz_prompt`/`_batch_quiz_prompt`에 출처 청크 원문 발췌(1,500자 컷) 주입. 배치는 같은 청크 공유 개념이 많아 원문 1회 게재 + `(원문 N)` 태그 참조 구조
- 검증 (course 24, session 21): 문항이 교재 고유 내용에 근거 — "곡선 y=x^3-3x^2+1 … 접선의 기울기"(교재 준비학습 문제 그대로), 무지개 지문·예제 1(sin x) 기반 문항. 기존(이름+한줄 설명만)에선 불가능하던 접지
- 관찰: ① start 1회 502 — 배치 문항 생성엔 재시도가 없음(추출 경로엔 있음), 재호출로 성공 — 재시도 추가는 승인 대기 ② 표지 지문 유래 노이즈 개념("무지개","물방울")도 출제됨 — 상류 노이즈 문제(v2 후보) 재확인 ③ "점 (,0)" — π 평문화 흔적(ISSUE-012 잔재)

### 추가 (같은 날): ISSUE-016 대응 — 문항 검증 패스 + 해설 정리
- 배치 생성 재시도 확장: ValidationError만 잡던 것에 ValueError(JSON 절단 — 실측 500) 추가
- 해설 정리: 프롬프트 규칙(1~2문장, 자기교정·내부참조 금지) + `_clean_explanation` 후처리(독백 마커 컷, "원문 N"→"교재", 350자 상한) — session 23부터 해설 청결 확인
- **문항 검증 패스 (3차 반복 끝에 완성)**: ① LLM에게 "훑고 판정" → 오답 mcq 통과(실패) ② 구조화 "직접 풀고 valid 판정" → **검수자가 정답을 옳게 계산해 놓고도 비교에서 오판**(스모킹건: my_answer='y=3x-1'인데 valid=true) ③ 최종 설계: **LLM은 my_answer만 산출, options[answer_index] 대조는 코드가 수행**(정규화+포함 매칭). 재생성분도 1회 재검증(2회 불합격 시 로그 후 사용 — 루프 방지)
- E2E (session 26): 검증이 배치에서 오답 mcq 2건 적발·재생성, **최종 mcq 4/4 수학적으로 정확** — 반복 실패하던 접선 문항(y=x²+x → y=3x-1) 포함. 진단 시작 14s→43s (검증 비용, 수용)
- 잔여: 검수 오탐(표현 차이로 정상 문항 재생성 — 비용만 소모, 무해), ISSUE-016 ③(채점 인정 범위)·④(노이즈 개념)는 미대응

### 추가 (같은 날): ISSUE-017 착수 — 씨앗 계약 구현 ①③④ 완료 (②는 팀 답변 대기)
- migration 0013: `chapters`/`sections` 테이블 + `concepts.key` + enrollments(floor/ceiling/floor_found/purpose)
- `seed/service.py` 신규 (ISSUE-004 스텁 → 실구현): `POST /api/seed/{course_id}/build` —
  ③ 커리큘럼 트리: 스캔 파트→chapters(order 10/20/30, gen_status pending 고정), 대표 개념→sections.concept_id 1:1
  ① key 슬러그: LLM 배치 생성 + 유니크화 + 폴백(concept-{id}) — course 24: 152개(LLM 140/폴백 12), 품질 양호("equation-of-tangent-line")
  ④ enrollment 확정 + mastery 초기값(mastered/todo/locked, 계약 표 매핑) 시드 JSON 반환 — 사용자 단위 concept_mastery 테이블 기록은 UUID 이관 시(테이블명이 lab 세션 BKT와 충돌)
- E2E (course 24): 챕터 8·절 28·enrollment 확정(floor=오답 났던 '접선의 방정식' — 의미 정확), mastery todo 2/locked 150
- 수정 1건: 시드가 "최신 세션" 대신 **진단 신호 최다 세션** 채택 (dev에 미응답 세션 누적 시 전부 locked 되는 결함 실측 후)
- 잔여: ② external_refs(팀 답변 대기), 챕터 제목 품질(스캔 파트가 "01"·"생각 열기" 같은 소제목을 파트로 잡은 흔적 — 스캔 변동성 계보), 하향 전파값(0.3)이 P_INIT과 동일해 todo/locked 구분 불가(ISSUE-015 재설계에서 해소)

### 다음 액션
1. 팀 회의: schema_feedback(§8 회신 포함)+seed_spec_draft+ii.md — external_refs 방식·UUID 시점 결정
2. ISSUE-015/005 통합 설계 (배치고사 + 학습 루프)
3. 커밋: `c2d70f9`까지 완료. **uncommitted: 스캔 보강 + 원문 주입 + ISSUE-016 대응 + 씨앗 계약 ①③④** (사용자 보류 중) / 푸시 대기 3커밋

---

## 2026-07-04 — Claude CLI — 정제 v1 설계 확정(ISSUE-014) + ISSUE-008/009 커밋

### 사용자 요청
- 파싱~그래프 저장 전체 흐름 설명 요청 → 정제 단계 필요성 제기("맞춤법·오타·서문 등 비학습 콘텐츠, 문서 성격 구분") → 브레인스토밍으로 v1 범위 합의 → ISSUE-013/014 기록 + 커밋 지시

### 추론 / 결정 (브레인스토밍 합의 사항)
- **정제 대상은 마크다운이 아니라 elements** — 청킹 1순위 입력이 elements이므로. elements는 PDF 시각 정보에서만 생성 가능(정제 텍스트로 재생성 불가)
- **2층 구조**: raw_text = 보존용 원본(불변), refined_elements = 운영용 원본. 정제 실수 시 재파싱 비용 없이 복구·재정제
- **removed 마킹 원칙**: 물리 삭제 금지 — 파서 오분류(본문을 header로 등)에 대비. 피해 비대칭 분석: 잘못 남김=소음(무해), 잘못 지움=내용 손실(치명) → 방어는 삭제 방향에만
- **LLM 스캔은 위치 판정만**: 본문 재생성 금지(환각 유입 차단). 출력은 요소 번호(본문 시작·제거 구간·파트 경계)와 프로파일 라벨뿐
- **프로파일(linked/enumerative/mixed)은 v1에서 저장만**: 오판 피해 0인 상태로 라벨 신뢰도를 실측한 뒤 v2에서 추출 분기·진단 전파·커리큘럼에 활용. 혼합 문서는 mixed + 필요 시 파트 단위로 해상도 확장
- 근거 실측: 정처기 course 12 첫 청크 anchor "(서문) ~ ▶ 상향식 비용 산정 기법" — 서문이 본문과 병합돼 LLM 유입(ISSUE-013). header/footer 60개는 전부 진짜 장식(Ⓒ×20, 챕터명, 페이지 번호) — 반복성이 교차검증 신호로 유효함 확인

### 한 일
- ISSUE-013 기록 (elements 청킹 파트 경계 규칙 부재)
- ISSUE-014 기록 (정제 v1 범위 — 이슈 표 참조)
- ISSUE-008/009 전체 커밋 `ed1da48` (**푸시 안 함** — 사용자 지시로 로컬만)
- 정처기 elements 원본 재확보(파싱 1회): 653요소 — 스크래치 `elements_full.json` (정제 모듈 오프라인 검증용)

### 결과 (같은 날 구현 + E2E 완료)
- 구현: migration 0011(`refined_elements` JSONB + `profile`), `refinement.py` 신규(규칙 마킹 + LLM 스캔 + 가드레일), `sectioning.chunk_elements`(removed 스킵 + part 경계 병합 금지), `service.ingest`(정제본 저장·정제 청킹)
- 오프라인 검증(정처기 653요소): 마킹 71개, body_start=14(수동 확인값 일치), profile=enumerative, 청크 26개에 (서문) 없음
- E2E(course 19 정처기 808s / course 20 미적분 66s, 둘 다 201·ready):
  - ① 서문 유래 개념: 정처기 **0개** (기존 course 12는 4개) ✓
  - ② 프로파일: enumerative / linked 정확 판정 ✓
  - ③ 개념 수: 정처기 801→1,011(교재 597→778), 미적분 110→111 — 열화 없음 ✓
- 관찰: 파트 경계 분리로 청크 21→26(정처기)·7→9(미적분). 미적분 첫 헤딩 이전 실내용은 보존됐고("도함수" 등 4개 정상) 표지 캡션 노이즈 2개("무지개") 유입 — 보수적 보존의 의도된 비용
- ISSUE-013·014 클로즈. 스캔 파트 판정은 실행 간 편차 존재(13개/12개) — 둘 다 무해 방향

### 추가 (같은 날): ISSUE-010 ① 임베딩 배치화 구현
- `solar.embed_batch()` + `service._embed_all()` 배치 프리페치 (64개/배치), resolve는 캐시 조회 + 미스 시 단건 폴백 — dedup 로직·결과 불변
- 미적분 E2E (doc 21): 132텍스트 → 3호출, 201/ready. 소형 문서라 총시간 개선은 미미(추출 LLM 지배적) — 대형 문서 실측은 다음 정처기 업로드 때
- 관찰: 추출 LLM 실행 편차로 개념 수 111→126 (교재 80→69, 보충 31→57) — 배치와 무관한 비결정성, 기존에도 존재(course 16: 110 vs 20: 111)

### 다음 액션
1. 정제 v1(`60e5787`) 커밋 완료 — ISSUE-010 ① 커밋 여부 + `ed1da48`부터 푸시 타이밍 사용자 결정 대기
2. v2 후보: 프로파일 활용(추출 분기·진단 전파), 표지 캡션류 잔여 노이즈, ISSUE-010 ②(백그라운드 잡)

---

## 2026-07-03 — Claude CLI — B(요소 기반 청킹) 프로덕션 도입 완료

### 사용자 요청
- A/B 비교 검증의 권고사항대로 진행 (A 유지 + B 프로덕션 도입)

### 한 일 / 변경 파일
- `core/llm/solar.py`: `parse_document()` → (마크다운, elements 배열) 반환
- `documents/sectioning.py`: `chunk_elements()` 신규 — header/footer/footnote 제외, heading1~3 경계 + 예산 병합, **요소 절대 비분할**(수식·표 원자성 구조 보장)
- `documents/service.py`: ingest가 요소 청킹 1순위, elements 비어 있으면 기존 마크다운 청킹 폴백. (A의 수식 복원 프롬프트 규칙도 유지)

### 검증
- 로컬: 저장된 수학 elements(559개)로 프로덕션 `chunk_elements` 실행 → 프로토타입과 동일(7청크, 노이즈 0, $$ 잘림 0), 빈 elements → 0청크(폴백 트리거) 확인
- **대형 플랫 문서 안전성**: 정처기 PDF 파싱 1회(653요소, heading1 195개) → 요소 청킹 21개(마크다운 경로와 동일, min/med/max 2925/3672/4017자) — 청크 폭발 없음, header/footer 60개 제외 효과
- **E2E (course 16)**: 수학 PDF 프로덕션 경로 섭취 성공(201, ready) — 로그로 요소 청킹 사용("추출 N/7") 확인, 개념 110개(교재 67 — 역대 최다, 노이즈 제거 효과 추정), 섹션 노드 3개, 푸터 잔재 개념 0개

### 부수효과 (dev DB)
- 미적분 코스 4개 누적 (13: 260128 파서 / 14: 기준선 / 15: A 테스트 / 16: B 프로덕션) — 16이 최신, 13~15는 실험 증거물로 정리 가능

### 다음 액션
1. 커밋은 사용자 지시 대기 (ISSUE-008/009 + 파서 버전 + A/B 반영 전체가 uncommitted)
2. 남은 이슈: ISSUE-010(임베딩 배치화), ISSUE-011(잔존 중복·앵커), ISSUE-012(A로 부분 완화 상태), ISSUE-004/005(seed·학습 루프)

---

## 2026-07-03 — Claude CLI — ISSUE-012 대응 2방식 비교 검증 (A: 프롬프트 정규화 vs B: 요소 기반 청킹)

### 사용자 요청
- 팀원 제안(B): "Solar 파서가 문단/표/그림/수식 요소로 나눠주니 청킹도 그에 맞춰라" + Claude 제안(A): 추출 프롬프트에서 평문화 수식 복원 — 두 방식을 **수학 PDF로만** 테스트·비교 (정처기 불필요)

### 실험 설계 (변인 통제)
| 실험 | 청킹 | 정규화 프롬프트 | 결과물 |
|---|---|---|---|
| 기준선 | 마크다운 | ✗ | course 14 (95개념) |
| B | 요소 기반(프로토타입) | ✗ | /tmp/b_extract.json (53타겟, 저장 안 함) |
| A | 마크다운 | ✓ (규칙 6 추가) | course 15 (88개념) |

### 사전 조사 — elements 응답 실물 (수학 PDF, 559요소)
- 분포: paragraph 350, heading1 64, list 31, equation 25, figure 25, footer 24, header 16, chart 15, table 7
- equation 요소는 깨끗한 LaTeX($$...$$) — 단 1건 오인식(복잡 레이아웃)
- **인라인 수식 평문화는 paragraph 요소 안에서 이미 발생** ("y=x2+x", "x2e-⌀"(원래 x²e⁻ˣ)) → B로 못 고침이 사전 확정
- heading1 오분류 존재: 문제 문장("곡선 y=sin x 위의 점...구하시오")이 heading1로 분류됨

### 결과 비교
**B (요소 기반 청킹)** — 청크 7개(현행 마크다운도 7개, 경계 대동소이):
- ✅ **페이지 헤더/푸터 노이즈 제거: 현행 7/7 청크 오염 → 0/7** (category 필터로 공짜)
- ✅ 수식/표 원자성 구조 보장 (요소를 절대 안 자름 — 현행은 문단 분할 운에 의존)
- ✅ 마크다운 역추론 휴리스틱(_MAX_REAL_PARTS 등) 제거 가능성
- ❌ 인라인 평문화 못 고침 (실증: "ex=4x"가 추출 개념명까지 그대로 관통)
- 단점: sectioning 재작성 + elements 응답 처리 필요(중간 규모), heading1 오분류 노이즈

**A (프롬프트 정규화, 규칙 1줄)** — 핵심 케이스 정밀 대조:
- 기준선(14): name "방정식 ex=4x의 실근 개수" / desc "방정식 ex=4x의 서로 다른 실근 개수를 구하는 문제" — 둘 다 평문
- A(15): name "방정식 ex=4x"(잔존) / **desc "지수함수 e^x와 일차함수 4x의 교점 개수 문제"(복원!)** — LLM이 의미를 정확히 복원, 단 이름은 원문 인용 형태 유지
- 집계 통계(^ 사용 수)는 회차 간 추출 변동(95 vs 88개념)에 묻혀 신뢰 불가 — 단일 실행 비교의 한계
- 장점: 비용 0, 이미 반영됨. 단점: 확률적(보장 없음), 이름 필드까진 약함, 잘못 복원(환각) 위험 소량

### 결론
- **A와 B는 경쟁이 아니라 상호보완** — A=수식 의미 복원(부분 성공, 유지 권장), B=구조 충실도(노이즈 제거 실익 명확)
- A는 프롬프트 규칙으로 **이미 프로덕션 반영됨** (uncommitted)
- B는 도입 가치 있으나 중간 규모 리팩터 — 우선순위는 팀 판단 (ISSUE-010 임베딩 배치화와 비교 필요). ISSUE-012는 A 반영으로 부분 완화, B는 별도 개선 후보로 유지

### 변경 파일
- `documents/service.py` — 추출 프롬프트에 수식 복원 규칙(6번) 추가
- 부수효과(dev DB): course 14(기준선), 15(A 테스트) — 미적분 중복 코스, 정리 가능

---

## 2026-07-03 — Claude CLI — Document Parse 최신 버전(260630)으로 교체

### 사용자 요청
- "업스테이지가 이번 달 파싱 업데이트했다는데 최신 쓰는지 확인" → "260630으로 알고 있다" → 최신으로 교체

### 추론 / 결정
- 실호출 검증 결과 **별칭("document-parse")은 260128(1월판)에 묶여 있고, 260630(6/30판)은 직접 지정 시에만 사용 가능** — "별칭이 자동으로 최신"이라는 공식 문서 안내가 실제로는 지연됨을 확인
- 처음엔 프로브 기반 버전 자동 추적 + `documents.parser_version` 기록(migration 0011)까지 구현했으나, **사용자가 과잉 설계로 판단("그냥 새 버전으로만 바꿔주면 되는 거")** → 전부 롤백(0011 downgrade + 파일 삭제)하고 **config 한 줄 교체만 유지**. 새 버전 출시 시 수동 갱신
- 참고: 260128 vs 260630 수식 처리 비교 → 동일 (ISSUE-012는 버전 문제 아님으로 판명, 이슈 표에 반영)

### 변경 파일
- `core/config.py`: `DOCUMENT_PARSE_MODEL = "document-parse-260630"` (별칭 지연 실측 코멘트 포함) — **이것만 최종 변경**

### 검증
- 별칭/명시 버전 각각 실호출로 응답 `model` 필드 대조 (260128 vs 260630)
- 롤백 후: `alembic current` = 0010, 문법 검사 통과
- **파이프라인 E2E 테스트 (course 14)**: 미적분 PDF 재섭취 성공(201, ready, 개념 95개). raw_text 길이 22,934자가 260630 직접 호출 산출물과 **정확히 일치**(구버전 260128은 23,187자) → 새 버전이 실제 경로로 흐르는 것 물증 확인

### 다음 액션
1. 커밋 여부 사용자 확인 (ISSUE-008+009+파서 버전 교체 전체)

---

## 2026-07-03 — Claude CLI — ISSUE-009 E2E 완료 (course 12) + 청킹 결함 수정

### 검증 결과 (course_id=12, document_id=12, 진단 session_id=9)
- 개념 801개 (교재 597 + AI 보충 204), 섹션 노드 16개(하위 9~48개씩), contains 엣지 562개
- **진단 메인 36개** (v1의 1,001개에서) — 진단 시작 시 문항 정확히 36개 생성, 765개 하위 잠금
- **오답 분기**: 섹션 "소프트웨어 구현"(하위 44) 의도적 오답 → 하위 정확히 3개만 잠금 해제+문항 생성, 나머지 41개는 잠금 유지+strength 0.30→0.177 하향 전파
- **정답 분기**: 섹션 "기억장치 및 네트워크 전송 방식"(하위 31) 정답 → 하위 31개 전부 자동 확정(strength 0.9, 문항 0건, 잠금 유지)

### E2E 중 발견·수정한 결함 (v2 재추출 전)
- **플랫 헤딩 청킹 폭발**: document-parse가 정처기 노트의 모든 소제목(■/▶/※)을 최상위 #으로 만들어, "파트 경계 병합 금지" 규칙이 모든 병합을 차단 → 126청크(LLM 호출 126회) + 청크당 타겟 2~7개로 팬아웃 미달 → 섹션 노드 형성 실패. **수정**: 최상위 제목 종류 > 12면 플랫 문서로 판정해 경계 규칙 해제(`sectioning._MAX_REAL_PARTS`), 청크 예산 8000→4000자(청크≈진단 섹션 단위). 실제 원문 로컬 테스트로 126→21청크 확인 후 재실행
- 진행 로그 부재로 "멈춤 vs 느림" 구분 불가했던 문제 → 추출 N/M·저장 100개 단위·Upstage 재시도 로그 추가(`uvicorn.error` 로거)
- 참고: v2 실행이 PC 절전으로 11시간 얼었다가 깨어나 정상 완주함 — 절전은 중단이 아니라 일시정지로 동작 확인

### 부수효과 (dev DB)
- course 12 = 최신 정처기 (course 3, 9는 구버전 증거물로 잔존 — 정리 가능)
- 진단 session 9에 테스트 답안 2건 (q42 오답, q59 정답)

### 수학 PDF 3유형 실증 결과 (course_id=13, document_id=13)
- 동아 미적분 05 도함수의 활용 (4.6MB, raw_text 23K자) → 개념 69개(교재 39+AI 30), 섭취 성공
- **조건부 계층의 우아한 퇴화 확인**: 소형 문서라 섹션 노드 2개만 생성(팬아웃 8~9), 나머지는 평평한 메인 20개 — 설계 의도대로 문서가 스스로 구조 결정
- 개념 품질 양호: 접선의 방정식, 변곡점, 이계도함수, 극값과 변곡점의 관계, 속도/가속도 등 단원 핵심 전부 추출. 선수개념(AI 보충 30개)도 수학 맥락 유지
- **한계 실증 (ISSUE-012 신규)**: 수식 평문화 — x²→"x2", eˣ→"ex". 예측했던 리스크가 그대로 확인됨. 부록/융합 코너의 노이즈 개념(IoT, 창의성 등)도 소량 유입
- 3유형 실증 완성: 정처기(구조 밀집형, 계층화) ✅ / 논문(course 2, 소형 비구조) ✅ / 수학(수식형, 퇴화 동작+수식 한계 확인) ⚠️✅

### 다음 액션
1. 커밋 여부 사용자 확인 (ISSUE-008+009 구현 전체)
2. ISSUE-010(임베딩 배치화 — 429 실측 근거 확보됨), ISSUE-012(수식), ISSUE-011(잔존 중복·앵커) 대기

---

## 2026-07-02 — Claude CLI — ISSUE-009 구현 (조건부 섹션 계층 + 진단 게이팅 확장) — E2E 진행 중

### 사용자 요청
- ISSUE-009 브레인스토밍 → "진단은 거칠게, 정밀 측정은 커리큘럼/학습 단계로" 방향을 사용자가 제안, Claude가 A(섹션 계층)+B(학습 중 정밀화=ISSUE-005)+C(오답 시 하위 샘플링) 조합으로 구체화
- 사용자 검증 질문 "정처기 아닌 다른 모든 PDF도 고려했나?" → **조건부** 섹션 노드로 설계 수정 (논문 등 소형 문서는 자동으로 기존 동작 유지), "수학·국어도 되나?" → 선언적 지식 문서면 과목 무관, 수학 PDF를 검증 셋에 추가하기로
- "그렇게 진행해줘" → 구현 착수

### 추론 / 결정 (합의된 설계)
1. **조건부 섹션 노드**: 청크 타겟 수 ≥ `SECTION_NODE_MIN_FANOUT`(8)이면 LLM이 지은 섹션 대표 개념을 depth 0으로 생성, 타겟들을 depth 1 + `kind='contains'` 엣지로 연결. 미달 청크는 섹션 노드 없이 타겟이 그대로 메인 → **문서가 스스로 구조를 결정** (정처기=계층화, 논문=기존 동작)
2. 섹션 노드 이름은 헤딩 원문 복사가 아니라 LLM이 "학습 주제로서의 개념명"으로 명명 (구조적 헤딩 대응)
3. **진단 게이팅 확장**: 메인 판정 = 선수도 아니고 contains 하위도 아닌 것. 정답 → 선수+contains 하위 전체 자동 확정(기존과 동일 원리). 오답 → 선수는 전부 + contains 하위는 **대표 N개만**(`BKT_GATED_CONTAINS_SAMPLE`=3) 잠금 해제 출제, 나머지 하위는 `propagate_down`으로 오답 신호만 반영하고 잠금 유지(거친 씨앗) — 학습 중 확인 루프(ISSUE-005)가 이후 정밀화
4. 파트 7문항 2단 게이팅은 채택 안 함 — 자동 확정 관대함이 지수적으로 커져 진단 무의미화. 섹션 1단(50~100문항 풀, 게이팅으로 실제는 더 적음)이 적정
5. learning 쪽은 `kind='prerequisite'` 필터가 이미 있어 contains 엣지 영향 없음(확인 완료)

### 한 일
- `core/config.py`: `SECTION_NODE_MIN_FANOUT=8`, `BKT_GATED_CONTAINS_SAMPLE=3`
- `documents/schemas.py`: `SectionConcept` + `ExtractionResult.section` 필드
- `documents/service.py`: 추출 프롬프트에 섹션 대표 개념 요구, `_persist_graph`에 조건부 섹션 노드 생성 + contains 엣지
- `diagnostic/repository.py`: `get_all_sub_ids`(prerequisite+contains 잠금 대상), `get_contains_child_ids`, `get_container_ids`
- `diagnostic/service.py`: `start()` 잠금 대상 확장, `_mark_subtree_known` 양쪽 엣지 순회, `_gate_after_answer` 오답 시 contains 샘플 출제 + 나머지 하향 전파

### 변경 파일
- `backend/app/core/config.py`, `backend/app/features/documents/{schemas,service}.py`, `backend/app/features/diagnostic/{repository,service}.py`

### 결과 / 검증 (진행 중)
- 문법 검사 통과, backend 정상 리로드
- 정처기 PDF 재추출(섹션 계층 버전) 컨테이너 내부 detached 실행 중 — 완료 시 메인 수(목표 50~100)·진단 시작 문항 수 검증 예정
- 수학 PDF 검증은 파일 확보 후 (사용자 제공 필요할 수 있음)

### 열린 이슈
- [ ] ISSUE-009 — 구현 완료, E2E 검증 대기

### 다음 액션
1. E2E: 재추출 후 메인 수 확인 → 진단 시작해서 문항 수·게이팅 동작 확인
2. 소형 문서(논문 스타일) 회귀 확인 — 섹션 노드가 안 생기고 기존 동작 유지되는지
3. 수학 PDF 3유형 실증

---

## 2026-07-02 — Claude CLI — ISSUE-008 1단계 구현 (섹션 분할 추출 + 출처 표시 + dedup) — E2E 검증 진행 중

### 사용자 요청
- 합의된 설계("넓이는 미리, 깊이는 JIT")의 1단계 구현 착수 지시. 추가 요구: **선수개념은 LLM이 만들거나 가져오는 것이므로 출처를 명확히 표시**할 것.

### 추론 / 결정
- 섹션 분할은 `bkt.py`처럼 순수 로직 모듈(`sectioning.py`)로 분리 — DB/LLM 비의존이라 단독 테스트 가능.
- 출처 구분은 LLM 자기보고가 아니라 **규칙 기반**: 섹션 추출의 타겟(root) = `source='document'` + 출처 섹션 앵커, 선수 노드로 새로 생기는 것 = `source='llm'`. 2단계 persist(타겟 전부 먼저 → 선수 연결)로 "교재에도 있는 개념이 llm 출처로 먼저 생기는" 순서 문제를 차단. dedup 병합 시 document 출처가 llm보다 우선(승격).
- 청크 병합 시 최상위 헤딩(파트)이 바뀌면 병합 금지 — 크로스 파트 선수관계 오류 재발 방지.
- 200자 미만 청크(목차 스텁, 파트 표지)는 LLM 호출 없이 폐기.

### 한 일
1. **migration `0010_concept_source.py`**: `concepts.source`(document|llm, default document) + `concepts.source_anchor`(text) — Docker에서 `alembic upgrade head` 적용 완료(`0010 (head)`)
2. **`documents/sectioning.py` 신규**: 마크다운 헤딩 파싱 → 섹션 → 문자 예산(8000자) 청크 병합/분할. 헤딩 없는 문서는 문단 분할 폴백. 로컬 단위 테스트로 병합/분할/폴백/극소문서 케이스 확인
3. **`documents/service.py`**: 전체 단일 호출 → 청크별 병렬 추출(semaphore 3, 청크당 1회 재시도) + 2단계 persist + `_merge_concept`(임베딩 dedup 병합, `CONCEPT_DEDUP_SIM_THRESHOLD=0.92`) + 커버리지 요구 프롬프트("하나도 빠짐없이", 외부 배경지식 선수 허용)
4. **`documents/repository.py`**: `add_concept`에 source/anchor, `get_concept`, `find_nearest_concept`(pgvector cosine)
5. **`core/config.py`**: `EXTRACTION_SECTION_CHAR_BUDGET=8000`, `EXTRACTION_MAX_CONCURRENCY=3`, `CONCEPT_DEDUP_SIM_THRESHOLD=0.92`
6. **스키마/프론트**: `ConceptOut`에 source/source_anchor, `types.ts` 동기화, `UploadPanel`에 출처 배지("교재: {섹션}" / "AI 보충 선수개념"). 컨테이너에서 `tsc --noEmit` 통과

### E2E 재추출 중 발견·수정한 실패 2건 (둘 다 실코드 수정)
- **document 4 실패**: LLM이 `prerequisites`를 객체 대신 문자열 배열(`["PERT","CPM"]`)로 반환 → `ConceptNode`에 `field_validator(mode="before")`로 문자열→노드 보정 추가 + 프롬프트에 객체 형식 명시
- **document 5 실패**: 개념 수십 개 연속 embed 호출로 Upstage **429 rate limit** → `solar.py` 전 엔드포인트에 `_post_retrying()`(Retry-After 존중, 지수 백오프, 최대 5회) 적용

### 변경 파일
- `backend/alembic/versions/0010_concept_source.py` (신규), `backend/app/features/documents/sectioning.py` (신규)
- `backend/app/features/documents/{models,repository,schemas,service}.py`, `backend/app/core/config.py`, `backend/app/core/llm/solar.py`
- `frontend/src/features/documents/types.ts`, `frontend/src/features/documents/components/UploadPanel.tsx`

### 결과 / 검증 (완료 — course_id=9, document_id=9)
- E2E 시도 5회 만에 성공 (HTTP 201, status=ready, 소요 ~17.5분). 각 실패가 실제 결함을 드러내 코드로 방어됨:
  - 4차: solar.py 수정이 uvicorn --reload를 트리거했는데 좀비 요청(7,8) 때문에 "Waiting for background tasks"에서 리로드가 멈춰 서버 다운 → `docker compose restart backend`로 해소. 5xx/타임아웃 재시도도 이때 추가
  - 5차(성공): 컨테이너 내부 detached 실행, 단독(동시 ingest 없음)
- **Before/After (Cursor 검증표 대비)**:
  - 개념 수: 20 → **1,457** (교재 출처 1,001 / AI 보충 선수 456)
  - 6장「기타 용어」: 전체 누락 → **커버** (클라우드 IaaS/PaaS, RAID 0~6, AJAX/JSON, 트리 순회 전위/중위/후위, PaaS-Ta 등 확인)
  - 기존 누락 세부 토픽 전수 확인: 선점형 스케줄링, 교착상태 4종, 페이징, TCP/UDP(헤더·플래그까지), 서브넷 마스크, JOIN 종류별(CROSS/Equi/Natural/Theta), GROUP BY, DDL, 방화벽, XSS 모두 존재
  - 출처 표시: document 개념 1,001개 전부 `source_anchor` 보유, llm 456개 구분 저장 — UI 배지 데이터 확보
  - 선수관계: 엣지 1,200개(교재→교재 563, →AI보충 616), 랜덤 12개 눈검사에서 의미적 타당("쉘←사용자 인터페이스", "SQL←관계형 데이터베이스" 등), 기존 같은 크로스 파트 오류 샘플에서 미발견
- **새로 드러난 문제**: ISSUE-009(메인 1,001개=진단 1,001문항, granularity), ISSUE-010(17분 소요), ISSUE-011(잔존 유사 중복·앵커 부정확) — 열린 이슈 표 참조

### 열린 이슈
- [x] ISSUE-008 — 1단계 구현+E2E 검증 완료, closed
- [ ] ISSUE-009 (신규 P1) / ISSUE-010 (신규 P2) / ISSUE-011 (신규 P3)

### 다음 액션
1. **ISSUE-009가 최우선** — 이대로면 course 9로 진단을 못 돌림. granularity 계층화(중간 노드) 또는 메인 선별 설계 필요 (사용자 논의)
2. 이번 구현 커밋 여부 사용자 확인
3. 2단계(커리큘럼 JIT 깊이 확장)는 ISSUE-005와 묶어 설계

---

## 2026-07-02 — Claude CLI — ISSUE-008 설계 브레인스토밍 (코드 변경 없음, 방향 확정)

### 사용자 요청
- ISSUE-008 개선 방향을 같이 브레인스토밍. 사용자가 직접 제안한 아이디어: "타겟/메인 개념은 섹션별로 빠짐없이 뽑되 깊이는 1~2단계만 → 진단(씨앗). 깊은 하위 개념은 커리큘럼 생성 때 챕터별 AI 호출 과정에서 그때그때 추가로 파고들기(lazy)."
- 커버리지 요구사항 확정: "이 자료로만 공부해도 누락 없이 학습되어야 함" — 메인 누락은 곧 학습 불가이므로 절대 안 됨. 교재 내용 + 교재 이해에 필요한 선수개념까지 전부. 정처기에 한정하지 않고 **어떤 자료를 넣어도** 동일하게 동작해야 함.

### 추론 / 결정 — 합의된 설계 ("넓이는 미리, 깊이는 JIT")

1. **업로드 시점**: raw_text가 이미 마크다운(document-parse 출력)이므로 헤딩 기준 섹션 분할 → 섹션별 추출 호출로 메인/타겟 개념을 **빠짐없이** 추출. 깊이는 직접 선수 1~2단계까지만.
   - 근거: 게이티드 진단이 `BKT_GATED_MAX_DESCENT=1`이라 오답이어도 1단계만 내려감 → 깊은 그래프를 업로드 때 만들어봤자 진단은 안 씀(순수 낭비였음).
   - 섹션별 호출이므로 크로스 파트 선수관계 오류(스키마←SDLC 등)도 구조적으로 해소.
2. **커리큘럼 시점(JIT 깊이 확장)**: 개념 X의 커리큘럼 챕터 생성 시, X의 출처 섹션 텍스트에서 하위 개념을 추가 추출해 그래프 확장. 학습 안 하는 개념의 깊이는 영원히 안 뽑음 → Solar 비용이 실제 학습 개념에만 쓰임.
3. **임베딩 기반 중복 병합 = 필수 전제**: lazy 확장으로 뽑힌 하위 개념이 업로드 때 이미 다른 메인의 선수로 존재할 가능성 높음(예: "정규화"). persist 전에 기존 개념과 코사인 유사도 검사 후 병합. embed는 이미 개념마다 수행 중이라 추가 비용 거의 없음.
4. **구현 전제**: `concepts`에 출처 섹션 앵커(헤딩 경로 또는 오프셋) 컬럼 필요 — 커리큘럼 시점에 "X의 챕터 텍스트"를 찾으려면 필수. 현재 스키마엔 없음.
5. **선수개념은 교재 밖 지식도 포함**: 교재를 이해하기 위한 외부 선수지식도 추출 대상(bridge 모드가 설명해주는 대상이 바로 이것).
6. **진단 문항 수 증가 수용**: 메인이 6개→30개 안팎이 되면 진단도 그만큼 길어지지만, 커버리지가 우선이라는 사용자 결정. (메인=파트 vs 메인=중주제 트레이드오프에서 "누락 없음"이 이김)
7. **ISSUE-005와의 시너지**: lazy 확장된 하위 개념은 진단을 안 거쳐 strength가 없음 → 학습 중 확인 루프(ISSUE-005)의 인출 채점이 이 노드들의 strength를 채우는 구조로 자연 연결. 두 이슈가 하나의 설계로 묶임.

### 한 일
- `backend/app/features/documents/service.py`, `core/config.py`, `core/llm/solar.py` 정독 — 원인 3개 특정: (1) 78K자 단일 호출 + max_tokens 미설정 → 출력 한계에서 ~20개로 압축, (2) 프롬프트에 커버리지/개수 요구 없음, (3) 마크다운 헤딩 구조를 안 씀
- 위 설계를 사용자와 합의 (코드 변경 없음)

### 변경 파일
- `docs/WORK_LOG.md` (이 항목, ISSUE-008 행 갱신)

### 결과
- ISSUE-008 구현 방향 확정. 구현 범위: 섹션 분할 추출 + 출처 앵커 저장 + 임베딩 dedup (업로드 경로) / JIT 깊이 확장 (커리큘럼 경로, ISSUE-005 설계와 함께 진행 가능)

### 검증
- 해당 없음 (설계 세션)

### 열린 이슈
- [ ] ISSUE-008 — 방향 확정, 구현 대기

### 다음 액션
1. 사용자 지시 시 구현 착수 — 1단계(업로드 경로: 섹션 분할 추출+앵커+dedup)부터, 2단계(커리큘럼 JIT 확장)는 ISSUE-005와 묶어 설계
2. 구현 후 course_id=3 재추출로 Before/After 커버리지 비교 (Cursor 검증표 재사용)

---

## 2026-07-02 — Cursor — Docker 기동 + PDF 개념 추출 검증 + Claude 동기화

### 사용자 요청
- 서비스 실행 (`docker compose up`)
- `[꿈꾸는라이언] 정보처리기사 실기 요약노트 (이론편).pdf` 업로드 후 추출된 20개 개념이 원문 대비 빠진 내용 없이 잘 나왔는지 검증
- 검증 결과를 Claude CLI에서 이어갈 수 있게 동기화

### 추론 / 결정
- 검증은 DB `documents.raw_text`(course_id=3, document_id=3, ~78,280자)와 API `GET /api/documents/courses/3` 응답의 20개 개념을 **목차 7파트 기준**으로 교차 대조.
- 원문 서두에 **프로그래밍 언어는 의도적으로 제외**되어 있음 → 미추출은 정상. 나머지 누락은 품질 이슈.
- 현재 추출 파이프라인 제약: `MAX_CONCEPT_DEPTH=2` (`config.py`), LLM이 전체 raw_text를 한 번에 20개 수준으로 압축 → **전체 커버리지 불가**가 구조적 원인.
- ISSUE-008로 등록하고 Claude CLI가 **추출 로직/프롬프트 개선**을 담당하도록 다음 액션 1순위로 올림.

### 한 일
1. `docker compose up --build -d` — db/backend/frontend 기동, migration `0009 (head)` 확인
2. course_id=3 원문·개념 대조 분석 (아래 결과 표)
3. `docs/WORK_LOG.md`에 본 세션 + ISSUE-008 기록 (Claude 인수인계)

### 변경 파일
- `docs/WORK_LOG.md` (이 항목, ISSUE-008, 다음 액션 갱신)

### 결과 — 업로드 데이터 스냅샷

| 항목 | 값 |
|------|-----|
| course_id | 3 |
| document_id | 3 |
| filename | `[꿈꾸는라이언] 정보처리기사 실기 요약노트 (이론편).pdf` |
| status | ready |
| concept_count | 20 |
| raw_text 길이 | ~78,280자 |

**PDF 목차 7파트 vs 추출 커버리지**

| 파트 | 원문 제목 | 추출 |
|------|-----------|------|
| 1 | 소프트웨어 구축 | ⚠️ SDLC+설계 일부만 (UML, 응집도/결합도, 테스트, COCOMO 등 누락) |
| 2 | 데이터베이스 | ⚠️ DBMS·스키마·정규화만 (E-R, 키, 관계대수, 트랜잭션, DDL/DML/DCL 누락) |
| 3 | 운영체제 | ⚠️ OS·기억장치·프로세스만 (스케줄링, 교착상태, 스레드, 페이징 알고리즘 누락) |
| 4 | 네트워크 | ⚠️ 네트워크·OSI·라우팅·프로토콜만 (TCP/UDP, IP/서브넷, 토폴로지, HTTP/DNS 등 누락) |
| 5 | 정보보안 | ⚠️ 3요소·AAA·암호화만 (방화벽, IDS/IPS, DoS/XSS/SQLi, 해시 상세 누락) |
| 6 | **기타 용어** | ❌ **전체 누락** (클라우드 IaaS/PaaS/SaaS, RAID, XML/JSON/AJAX, 트리순회, SPICE 등) |
| 7 | SQL문 활용 | ⚠️ SQL 개념 1개만 (SELECT/JOIN/GROUP BY/HAVING/UNION/DCL 실전 문법 누락) |

**추출된 depth 0 메인 6개** (방향은 맞음): SDLC, DBMS, OS, 네트워크, 정보 보안, SQL

**그래프 품질 이슈**
- 이름 중복: `데이터베이스 (DBMS)`(depth 0) vs `데이터베이스`(depth 1)
- 선수관계 오류: `스키마`·`데이터베이스`(depth 1)의 선수가 **SDLC**로 잡힘 → 원문상 **DBMS**가 맞음
- 전체 커버리지 추정: 파트별 핵심 키워드 **15~25%** — 실기 시험 대비 **불충분**

**종합:** 「큰 주제 뼈대」는 잡혔으나 **「빠진 내용 없이」는 아님**. 특히 6장 전체·SQL 실전·각 파트 세부 토픽 대거 누락.

### 검증
- `docker compose ps` → db(healthy), backend:8000, frontend:5173
- `docker compose exec backend uv run alembic current` → `0009 (head)`
- `curl.exe` → `/docs` 200, `:5173` 200
- `GET /api/documents/courses/3` → concept_count=20 확인
- `documents.raw_text` 직접 대조 (목차·각 파트 본문)

### 열린 이슈
- [ ] **ISSUE-008 (신규, P1)** — 개념 추출 품질/커버리지 부족. Claude CLI가 개선 착수.

### 다음 액션 (Claude CLI용 — ISSUE-008 개선 방향 제안)

1. **파트별 분할 추출**: 목차 7파트(또는 `##`/`#` 헤딩) 단위로 LLM 호출 후 병합 — 78K자 한 번에 20개로 압축하지 않기
2. **6장「기타 용어」강제 포함**: 클라우드·RAID·XML/JSON/AJAX·트리순회·SPICE 등 최소 개념 세트 명시
3. **SQL 파트**: DDL/DML/DCL, JOIN, GROUP BY/HAVING, UNION 등 실기 빈출을 별도 개념으로
4. **선수관계 검증**: 추출 후 `prerequisites`가 같은 도메인(파트) 내인지 휴리스틱/LLM 2차 패스
5. **이름 중복 방지**: `데이터베이스` vs `데이터베이스 (DBMS)` 등 동의어 병합 규칙
6. (선택) `MAX_CONCEPT_DEPTH`·개념 수 상한 재검토 — 문서 특성에 따라 동적 조정
7. 개선 후 **course_id=3 재업로드 또는 재추출**로 Before/After 비교

**관련 코드**
- `backend/app/features/documents/service.py` — `_extraction_prompt()`, `_extract_concepts()`, `ingest()`
- `backend/app/core/config.py` — `MAX_CONCEPT_DEPTH=2`

**테스트 데이터**: course_id=3, Docker 이미 기동 중 (`localhost:5173/lab/documents`)

---

## 2026-07-02 — Claude CLI — ISSUE-002 커밋 + 푸시

### 사용자 요청
- "1번 내용 내가 직접 커밋이랑 푸시 할거니깐 커밋 메세지 어떻게 쓸까" → 커밋 메시지 제안 후, "커밋 후에 푸시해줘"로 직접 수행 지시

### 추론 / 결정
- 리네임(`materials→documents`)이 `git add -A`로도 rename으로 잘 인식되는지 먼저 `git status --porcelain`으로 확인 후 스테이징 — `router.py`, `UploadPanel.tsx`, `types.ts`는 git이 자동으로 rename(R)으로 인식함을 확인.
- `__pycache__/`는 `.gitignore`에 이미 포함되어 있어 별도 제외 처리 불필요했음(확인만 하고 그대로 진행).
- 커밋 타입은 `refactor:`로 선택 — 리네임/스키마 정렬이 핵심이고 auth 스텁·버그 수정 2건은 같은 작업의 부산물이라 판단.
- 커밋·푸시는 사용자가 이번 세션에서 명시적으로 지시했으므로 [[feedback-metalearn-collaboration-style]] 규칙(사용자 지시 전 커밋 금지)에 어긋나지 않음.

### 한 일
1. `git add -A -- <경로들>`로 diagnostic/learning 수정, materials 삭제, documents/auth 신규, migration 0009, docs/ 전체 스테이징
2. `git commit`(refactor: 팀 스키마 정렬 + BKT/커리큘럼 버그 수정, 본문에 리네임 목록 + fix 2건 요약)
3. `git push origin feat/parsing`

### 변경 파일
- 38개 파일 커밋 (리네임 3건 자동 인식, 신규 8개, 삭제 4개, 수정 나머지)
- 커밋 해시: `33a672d`

### 결과
- `feat/parsing` 로컬=원격 동기화, working tree clean
- ISSUE-002 완전 종료

### 검증
- `git status` → "nothing to commit, working tree clean"
- `git push` → `5dbf7b9..33a672d  feat/parsing -> feat/parsing` (rejected 없이 성공)

### 열린 이슈
- [x] ISSUE-002 — 커밋+푸시 완료, 완전 종료

### 다음 액션
1. Cursor가 다음에 이 파일을 열면 `33a672d` 커밋 내역을 이미 반영된 상태로 인지해야 함 — 이 항목이 그 근거
2. ISSUE-005(학습 확인 루프), ISSUE-004(seed formalize) 순으로 다음 후보

---

## 2026-07-02 — Claude CLI — ISSUE-007 수정 (커리큘럼 모드가 선수 강도 무시하던 문제)

### 사용자 요청
- "ISSUE-007 지금 고쳐줘"

### 추론 / 결정
- 사용자 철학 원문 기준으로 분기 규칙을 다시 세움: X 자신이 강하면(≥0.5) → focused(기존과 동일). X가 약해도, 직접 선수 중 "약한 것"이 하나도 없으면(선수가 전부 이미 앎, 혹은 애초에 선수가 없음) → **focused**(신규). X도 약하고 약한 선수도 있으면 → bridge(기존과 동일, 단 해당 약한 선수만 포함).
- 구현 방법 선택: `high` 판정에 `or not weak_prereqs`를 추가하는 방식 채택. 대안으로 "모드는 그대로 X 강도로만 정하고 bridge일 때 약한 선수가 없으면 그 섹션만 생략"하는 방식도 있었지만, 그러면 응답의 `mode` 필드가 "bridge"인데 실제로는 100% 본문인 상태가 되어 프론트/로그에서 오해를 유발할 수 있음 → mode 필드 자체를 focused로 바꾸는 게 더 정직하다고 판단.
- `_weak_prerequisites()`의 `return weak or direct` 폴백 제거 — 이 폴백이 있으면 "weak 리스트가 비었을 때 전체 선수를 돌려주는" 이상한 의미가 되어 위 mode 판정과도 모순됨. 제거 후 `weak`(빈 리스트 가능)를 그대로 반환하도록 단순화.
- 세션 없는 경우(`session_id is None`)의 기존 보수적 fallback(직접 선수 전체를 weak로 간주)은 그대로 유지 — 이건 "모르니까 안전하게 bridge" 케이스라 이번 이슈와 무관.

### 한 일
- `backend/app/features/learning/service.py`
  - `generate_curriculum()`: `weak_prereqs`를 먼저 계산하고 `high = score >= LEARNING_HIGH_THRESHOLD or not weak_prereqs`로 변경, `used_prereqs`도 `weak_prereqs` 재사용
  - `_weak_prerequisites()`: `return weak or direct` → `return weak` (직접 리스트 컴프리헨션을 그대로 반환)
- `ast.parse`로 문법 확인
- 이미 떠 있는 backend 컨테이너(`--reload`)로 실제 API 재검증 (아래 검증 항목)

### 변경 파일
- `backend/app/features/learning/service.py`
- `docs/WORK_LOG.md` (이 항목, ISSUE-007 closed, 다음 액션 갱신)
- `docs/CLAUDE_CONTEXT.md` (§3 ⑤, §7 bridge/focused 행 갱신)

### 결과
- concept 1(X strength 0.043, 직접 선수 concept 2가 실제로 0.885까지 앎) → **focused**로 정정됨 (수정 전엔 bridge였음)
- 같은 concept 1을 대상으로, 선수(concept 2) strength를 일시적으로 0.2로 낮춰서(DB 직접 UPDATE, 검증 후 원복) 재확인 → **bridge**로 정상 전환, `prerequisite_names: ["다중 모달 융합"]`로 실제 약한 선수만 정확히 표기됨
- concept 3(X strength 0.9507, 애초에 강함) → 기존과 동일하게 focused, 회귀 없음 확인

### 검증
- `POST /api/learning/curriculum {concept_id:1, session_id:5, force_regenerate:true}` (수정 후, 선수 strength=0.885 그대로) → `mode: focused, prerequisite_names: []`
- DB에서 `concept_mastery.strength`(concept_id=2)를 0.2로 임시 변경 → 동일 요청 재실행 → `mode: bridge, prerequisite_names: ["다중 모달 융합"], block count: 7`
- 검증 직후 concept 2 strength를 실제 진단 결과값(0.8852459016393444)으로 원복 — 세션 5의 씨앗 데이터가 실제 답안 제출 결과와 다시 일치하도록 정리함
- `POST /api/learning/curriculum {concept_id:3, session_id:5}` (회귀 확인) → 여전히 `mode: focused`

### 열린 이슈
- [x] ISSUE-007 — 수정 + 두 분기(focused/bridge) 모두 실제 API로 재검증 완료. 완전 종료.

### 다음 액션
1. ISSUE-002 커밋은 여전히 사용자 확인 대기
2. 학습 중 확인 루프(ISSUE-005), seed formalize(ISSUE-004) 순으로 다음 후보

---

## 2026-07-02 — Claude CLI — 핵심 제품 루프 실제 E2E 검증 (Docker+DB, 코드 변경 없음)

### 사용자 요청
- "변경 사항 진행 하지말고 내 서비스 어떤지 한번 검증 해줘" — 사용자가 진단(수준 파악) 철학을 직접 다시 설명: A 문제 틀림→A 모름, 선수지식도 모르면 선수 뼈대부터 쌓고 A 설명(bridge), A는 약해도 선수는 알면 본문(A)만 집중(focused) — 개념마다 다르게 판단, 전원에게 선수를 깔지 않음. 이 씨앗으로 커리큘럼을 만든다는 전체 흐름이 실제로 동작하는지 확인 요청.

### 추론 / 결정
- 이미 떠 있던 Docker 컨테이너(`docker ps`로 확인, 47시간 전 기동)를 재사용하기로 결정 — `docker-compose.yml`에 `./backend:/app` 바인드 마운트 + `--reload`가 걸려 있어 방금 고친 ISSUE-001 수정사항이 이미 반영돼 있음을 먼저 확인 후 진행.
- 새 PDF를 업로드하는 대신 이미 존재하는 course_id=2("음향 논문", status=ready, 10개 개념)를 재사용 — 실제 Solar 파싱으로 만들어진 진짜 데이터라 (1)번 검증(업로드→파싱→그래프)을 새로 돌릴 필요 없이 이미 증명된 상태였음. 불필요한 Solar API 비용도 피함.
- 진단 세션은 실제로 새로 시작해서(session_id=5) 답을 의도적으로 섞어 제출 — 일부러 틀리고 일부러 맞혀서 게이티드 로직의 두 분기(정답→서브트리 확정, 오답→직접 선수 1단계 unlock)를 모두 관찰.
- 각 정답/오답 제출 후 API 응답만 보지 않고 `docker compose exec db psql`로 `concept_mastery`/`diagnostic_questions` 테이블을 직접 조회 — API 응답 JSON만으로는 "locked" 플래그나 "언제 질문이 생성됐는지"가 안 보여서, 게이팅이 진짜 DB 레벨에서 의도대로 동작하는지 확인하려면 직접 쿼리가 필요하다고 판단.
- 커리큘럼 생성까지 실제로 호출해서 bridge/focused 분기를 확인하던 중, concept 1의 선수(concept 2)가 이미 강하게 알려진 상태(strength 0.885)인데도 bridge 모드가 나오고 "약한 선수개념"이라고 표기되는 걸 발견 → 우연이 아닌지 확인하려고 `learning/service.py` 소스를 직접 읽어서 원인을 특정(`_weak_prerequisites()`의 `weak or direct` 폴백, 그리고애초에 모드 자체가 X의 strength만 보고 결정되는 구조).

### 한 일
1. `docker ps` / `docker compose exec backend uv run alembic current` — 컨테이너 상태 및 migration 버전(0009, head) 확인 → ISSUE-003 우려 해소
2. `GET /api/documents/courses`, `/api/documents/courses/2` — 기존 실제 업로드 데이터로 개념+선수지식 그래프 확인 (10개 개념, 5개 메인+5개 직접 선수, depth_level 0/1)
3. `POST /api/diagnostic/start` (course_id=2) → session_id=5, 메인 5개 개념만 배치 출제 확인
4. 답 6개를 실제로 제출(`POST .../answer`): 메인 개념 중 2개(concept 1, 7)는 의도적 오답, 나머지 3개(concept 3, 5, 9)는 정답, 오답으로 unlock된 선수(concept 2, 8)는 정답 제출 → 세션 완료(done=true, 10/10 resolved)까지 전 구간 무크래시 확인
5. 매 단계마다 `concept_mastery`/`diagnostic_questions` 테이블 직접 쿼리로 `locked`/`resolved`/`answered_count`와 실제 질문 생성 시점 대조
6. `POST /api/learning/curriculum`을 concept_id=1(약함, 0.043)과 concept_id=3(강함, 0.9507) 둘 다 호출해 bridge/focused 응답 비교
7. `backend/app/features/learning/service.py` 전체 읽고 모드 분기·`_weak_prerequisites()` 로직 재확인 (코드 수정은 안 함)

### 변경 파일
- 없음 (코드 변경 없음 — 사용자가 명시적으로 요청)
- 문서: `docs/CLAUDE_CONTEXT.md` §3·§7 상태 갱신, `docs/WORK_LOG.md` 이 항목 + 열린 이슈 표(ISSUE-001 E2E 확인 완료로 격상, ISSUE-003 closed, ISSUE-007 신규 등록)
- 부수효과(DB 데이터, 코드 아님): dev DB에 진단 세션 `session_id=5`, 커리큘럼 레코드 2건(concept 1, concept 3)이 테스트 결과물로 생성됨 — 실제 코드/스키마 변경은 아니지만 참고용으로 남김. 필요하면 정리해도 무방.

### 결과 — 사용자가 설명한 철학 대비 실제 동작
| 사용자가 설명한 로직 | 실제 검증 결과 |
|---|---|
| PDF→파싱→개념+선수지식 그래프 | ✅ 확인 (기존 실사용 데이터, 10개 개념, prerequisite 엣지 정상) |
| A 틀리면 A 모름, 선수도 모르면 선수부터 확인 | ✅ 확인 — 오답 시 직접 선수가 `locked:false`로 풀리고 그 즉시 새 문제가 지연 생성됨(concept 1 오답→concept 2 문제 생성, concept 7 오답→concept 8 문제 생성) |
| A는 맞고 선수도 안다고 볼 수 있으면 생략 | ✅ 확인 — 정답 시 직접 선수가 `resolved:true, strength=0.9, answered_count=0`(질문 자체를 생성 안 함)으로 자동 확정, `locked:true` 유지(출제 화면엔 안 나옴) |
| 씨앗(개념별 프로필) 완성 | ✅ 확인 — 세션 종료 시 10개 개념 전부 `resolved:true`, 개념마다 실제 채점 결과를 반영한 서로 다른 strength |
| **A는 약해도 선수는 알면 → 본문(A)만 집중** | ⚠️ **불일치 발견 (ISSUE-007)** — concept 1은 strength 0.043(약함)인데 그 직접 선수(concept 2)는 사용자가 방금 정답으로 맞혀 strength 0.885(충분히 앎)까지 올라간 상태. 사용자 철학대로면 이건 focused(본문만)여야 하는데, 실제로는 **여전히 bridge 모드**로 응답하고 "선수개념: 다중 모달 융합" 챕터를 그대로 포함시킴. 원인: `generate_curriculum()`이 모드를 결정할 때 X 자신의 strength만 보고(`score >= 0.5`), 선수의 상태는 전혀 고려하지 않음. 게다가 `_weak_prerequisites()`가 "약한 선수가 하나도 없으면 그냥 전체 직접 선수를 돌려준다"는 폴백(`weak or direct`)을 갖고 있어서, 강한 선수도 "아직 약한 선수개념"이라고 LLM 프롬프트에 그대로 들어감. |
| bridge = 선수+본문, focused = 본문만 (모드 자체의 콘텐츠 구성) | ✅ 확인 — bridge 응답은 "선수개념: …" 챕터 + "메인 개념: …" 챕터 혼합(6블록), focused 응답은 메인 개념 챕터만(4블록), `prerequisite_names`도 focused에선 빈 배열 |
| 답안 채점 API가 안 죽는지(ISSUE-001) | ✅ 확인 — 실제 답안 6건 전부 정상 채점, 진단 세션 완주 |

### 검증
- `docker compose exec backend uv run alembic current` → `0009 (head)`
- `curl .../api/documents/courses/2` → 개념 10개, prerequisite_ids 정상
- `curl -X POST .../api/diagnostic/start` → session 5 생성, 메인 5문항 배치 생성 확인
- `curl -X POST .../questions/{id}/answer` × 6회 → 전부 200 응답, 크래시 없음, `is_correct`/`strength` 정상 갱신
- `docker compose exec db psql ... concept_mastery` × 2회(중간/최종) → `locked`/`resolved` 전이가 게이팅 로직과 정확히 일치
- `docker compose exec db psql ... diagnostic_questions` → 지연 생성된 선수 문항(concept 2, 8)이 오답 시점에만 생성됐음을 타임라인으로 확인
- `curl -X POST .../api/learning/curriculum` (concept 1, concept 3) → bridge/focused 블록 구성 비교, `learning/service.py` 소스 재확인으로 원인 특정

### 열린 이슈 (이번에 생기거나 남은 것)
- [x] ISSUE-001 — 이번 세션에서 실제 API E2E까지 확인 완료 (완전 종료)
- [x] ISSUE-003 — migration 걱정 해소 (이미 0009 head 적용됨, closed)
- [ ] **ISSUE-007 (신규, P1)** — 커리큘럼 모드 분기가 선수지식 강도를 반영 안 함 + `_weak_prerequisites()` 폴백이 강한 선수를 "약함"으로 오표기. 사용자가 명시한 제품 철학과 직접 충돌하는 부분이라 우선순위 높게 등록.

### 다음 액션
1. 사용자 확인 필요: ISSUE-007을 어떻게 고칠지 방향 결정 필요 — (a) 모드 결정 자체에 선수 강도를 반영할지(예: X 약함+선수도 약함일 때만 bridge, 선수가 이미 강하면 X가 약해도 focused), (b) 아니면 모드는 X 강도로만 결정하되 `_weak_prerequisites()`의 fallback만 없애서 "약한 선수 없으면 브릿지 섹션 자체를 생략"할지 — 사용자의 원래 설명("A는 약하지만 선수는 안다 → 본문만")은 (a)에 더 가까움
2. ISSUE-002(커밋), ISSUE-004(seed), ISSUE-005(학습 확인 루프) 등은 그대로 대기

---

## 2026-07-02 — Claude CLI — ISSUE-001 (BKT 채점 크래시) 수정

### 사용자 요청
- "ISSUE-001부터 수정해줘"

### 추론 / 결정
- 이전 세션에서 이미 원인을 정확히 특정해둔 상태(`service.py:117-118`의 `bkt.BKTParams(strength_init=...)` 호출 vs `bkt.py:18`의 dataclass 필드 `p_init`)라 원인 재조사 없이 바로 수정.
- 수정 방향은 `strength_init` 인자명을 `p_init`으로 맞추는 것(반대로 `bkt.py`의 dataclass 필드를 `strength_init`으로 바꾸는 방향은 채택 안 함) — `bkt.py`는 "순수 로직, DB 비의존"이라고 파일 docstring에 명시돼 있고 `p_init/p_transit/p_slip/p_guess`는 BKT 표준 표기(§ 파일 상단 주석)라서 DB 컬럼명(`strength`) rename과 별개로 유지하는 게 맞다고 판단. 즉 이번 리네임 작업(`p_known`→`strength`)이 실수로 BKT 내부 파라미터명까지 건드린 것이었고, 그걸 원복하는 게 올바른 수정.
- Docker/DB 없이 코드 레벨 검증만 수행 (풀 E2E는 안 돌림) — 그래서 상태 표기를 "✅ 구현 완료"가 아니라 "✅ 수정 완료, E2E 미검증"으로 남김.

### 한 일
- `backend/app/features/diagnostic/service.py:117-118` — `bkt.BKTParams(strength_init=...)` → `bkt.BKTParams(p_init=...)`로 수정 (들여쓰기 오류도 같이 정리)
- `ast.parse`로 두 파일 문법 검사
- `bkt.py`를 직접 import해서 `BKTParams(p_init=...)` 생성 + `update()` 호출까지 정상 동작 확인
- 비교용으로 옛 방식(`strength_init=...`)이 실제로 `TypeError`를 던지는지 재현해 버그가 진짜였음을 재확인
- `CLAUDE_CONTEXT.md` §3·§7 상태 표, `WORK_LOG.md` 열린 이슈 표(ISSUE-001 → closed) 갱신

### 변경 파일
- `backend/app/features/diagnostic/service.py` (버그 수정)
- `docs/CLAUDE_CONTEXT.md` (§3, §7 상태 갱신)
- `docs/WORK_LOG.md` (이 항목, ISSUE-001 상태 갱신)

### 결과
- `BKTParams` 생성 및 `bkt.update()` 호출이 코드 레벨에서 정상 동작 확인됨
- `backend/app/features/diagnostic/repository.py:100`의 `create_masteries(strength_init=...)`는 별개 함수 파라미터라 원래부터 버그 아니었음 — 그대로 유지

### 검증
- `python -c "ast.parse(...)"` — 문법 OK
- `python -c "from app.features.diagnostic import bkt; bkt.BKTParams(p_init=0.3, ...); bkt.update(...)"` — 정상 동작 (`update() OK: 0.646...`)
- 동일 스크립트에서 `BKTParams(strength_init=...)` 호출 시 `TypeError: unexpected keyword argument 'strength_init'` 재현 → 수정 전 상태가 실제로 깨져 있었음을 재확인
- **미검증**: FastAPI/DB 붙여서 실제 `/api/diagnostic/answer` 엔드포인트 호출까지는 안 해봄 (`fastapi` 모듈이 이 세션의 파이썬 환경에 없어서 서비스 레이어 전체 임포트 불가 — `uv`/Docker 환경에서 별도 확인 필요)

### 열린 이슈
- [x] ISSUE-001 — 코드 수정 완료. E2E 미검증이므로 완전 종료는 아님 (WORK_LOG 표에 "closed (E2E 미검증)"로 표기)

### 다음 액션
1. Docker 기동 후 실제 진단 플로우(세션 시작 → 답안 제출)로 ISSUE-001 E2E 확인
2. 사용자 확인 후 ISSUE-002(커밋) 등 다음 이슈 진행

---

## 2026-07-02 — Claude CLI — 세션 인수인계 로그 (Cursor 전환 대비 상세 기록)

### 사용자 요청
- "동기화 후 작업 시작" (처음엔 git 동기화로 오해 → 사용자가 "커서가 만든 md 파일 내용을 너도 이해하라는 뜻"이라고 정정)
- 이후 "내가 너랑 작업한 내용도 커서가 알아야 하니 너도 커서랑 동기화해야 해" → 문서에 되먹임 요청
- "피드백이나 선택/작업 부여 물어볼 때도 한국어로" → 응답 언어 확정 (AskUserQuestion 포함)
- 지금: "커서로 넘어가도 작업 내용 안 달라지게 로그·추론 상세히 작성" (이번 항목)

### 추론 / 결정
- **git 동기화를 먼저 확인한 이유**: "동기화"가 git pull을 뜻하는지 문맥상 불확실 → `git fetch` + `git log origin/feat/parsing`로 원격에 새 커밋 없음을 먼저 확정한 뒤 나머지 작업 진행. (결과: 새 커밋 없음, 로컬이 원격보다 앞서 있는 게 아니라 **커밋 안 된 변경**이 쌓여 있는 상태였음)
- **문서 내용을 코드로 직접 재검증한 이유**: `CLAUDE_CONTEXT.md`는 Cursor가 작성한 문서라 실제 코드(특히 rename 작업 중인 uncommitted 상태)와 어긋났을 가능성이 있다고 판단 → Explore 서브에이전트로 7개 핵심 주장(게이티드 BKT, bridge/focused 분기, ingestion, config 임계값, seed/auth 스텁 여부, 학습 확인 루프 미구현)을 코드에서 직접 확인. 문서를 그대로 믿지 않고 검증하는 게 `CLAUDE_CONTEXT.md` §12 "README만 믿지 말고 코드 확인"과 같은 원칙이라 판단.
- **ISSUE-001 (BKT 버그)을 바로 고치지 않은 이유**: 사용자가 아직 "뭐부터 할지" 명시 지시를 안 한 상태 → 최소 diff·무단 변경 금지 원칙상 발견만 보고하고 우선순위 선택은 사용자에게 맡김. (AskUserQuestion으로 두 번 물었으나 응답 없이 다른 지시로 전환됨 — 아직 미확정)
- **문서에 로그를 직접 쓰기로 한 이유**: Cursor는 Claude의 대화 메모리를 못 읽으므로, 세션에서 발견한 사실(버그, 검증 결과)은 반드시 공유 파일(WORK_LOG.md)에 남겨야 인수인계가 됨. Claude 자체 메모리(`~/.claude/.../memory/`)에는 "동기화 절차가 이렇게 바뀌었다"는 워크플로우 규칙만 남기고, 프로젝트 사실 정보는 전부 이 파일에 기록.

### 한 일
1. `git fetch origin` + `git log` 비교 → `feat/parsing`은 `origin/feat/parsing`과 완전히 동기화, 새로 pull할 팀원 커밋 없음을 확인
2. `git status` / `git diff --stat` → uncommitted 변경 목록 전수 파악 (materials 삭제 5파일, documents 신규, diagnostic/learning 수정 9파일, auth 신규 2파일, migration 0009 신규)
3. Explore 서브에이전트로 `CLAUDE_CONTEXT.md` §1~12 주장 7개 항목을 코드와 교차검증 → 전부 일치, 단 하나 불일치 발견
4. **ISSUE-001 직접 재현 확인**: `backend/app/features/diagnostic/service.py:117-118`의 `_params()`가 `bkt.BKTParams(strength_init=settings.BKT_P_INIT, ...)`로 호출하지만, `backend/app/features/diagnostic/bkt.py:18`의 `BKTParams` dataclass 필드는 `p_init`. `_params()`는 답안 채점 경로(`service.py:199`)에서 호출되므로 답안 제출 시 `TypeError` 크래시 확정. (참고로 `repository.py:100`의 `create_masteries(strength_init=...)`는 별개 함수라 버그 아님 — `_params()` 호출부만 문제)
5. 최초엔 `CLAUDE_CONTEXT.md` §13에 로그 기록 → 이후 Cursor가 세션 중 파일을 `CLAUDE_CONTEXT.md`(고정 맥락) / `WORK_LOG.md`(일지, 이 파일)로 분리 재구조화 → 이 항목부터는 새 규칙(WORK_LOG 맨 위 append)을 따름

### 변경 파일
- 코드 변경 **없음** (이번 세션은 읽기·검증만 수행, 실제 수정은 하지 않음)
- 문서: `docs/CLAUDE_CONTEXT.md` §13에 로그 추가했었으나, 이후 Cursor의 문서 분리 작업으로 해당 내용은 제거·`WORK_LOG.md`로 대체됨 (아래 "2026-07-02 — Cursor — 문서 분리" 항목 참고)

### 결과
- `ISSUE-001`은 **여전히 미수정** 상태로 남아 있음 (재현만 확인, 코드 수정 안 함)
- uncommitted 변경사항(`ISSUE-002`)도 그대로 미커밋 상태
- 사용자와 나눈 대화에서 확정된 협업 규칙: (1) 한국어로만 대화·질문, (2) 세션 내 발견 사항은 이 파일에 기록해서 Cursor와 공유, (3) 사용자가 명시적으로 지시하기 전엔 버그 수정·커밋 등 실질적 코드 변경을 먼저 하지 않음

### 검증
- `git fetch origin` → 새 커밋 없음 확인
- `git status --porcelain backend/app/features/auth/` + `git ls-files` → auth의 `__init__.py`/`router.py`는 기존 커밋(b3bc4ed) 소속, `models.py`/`repository.py`만 신규임을 라인 단위로 확인
- `backend/app/features/diagnostic/service.py:111-122`, `bkt.py:16-21`, `repository.py:100,108` 직접 Read로 대조 → ISSUE-001 필드명 불일치 재확인

### 열린 이슈
- 변동 없음. `ISSUE-001~006` 스냅샷(상단 "열린 이슈" 표) 그대로 유효. 이번 세션에서 새로 발견한 이슈는 없음 (ISSUE-001은 이전에 이미 이 세션에서 최초 발견 후 등록됨).

### 다음 액션
1. **사용자 결정 대기**: ISSUE-001 수정 / uncommitted 커밋(ISSUE-002) / migration 0009 적용 확인(ISSUE-003) / 학습 확인 루프(ISSUE-005) / seed formalize(ISSUE-004) 중 우선순위 미확정 — 다음 세션(Cursor든 Claude CLI든) 시작 시 사용자에게 재확인 필요
2. (제안) 리스크·되돌리기 난이도가 가장 낮고 P0인 ISSUE-001부터 처리하는 게 합리적이라고 판단되나, 사용자 확답 전엔 착수하지 않음

---

## 2026-07-02 — Cursor — 문서 분리 (CLAUDE_CONTEXT / WORK_LOG)

### 사용자 요청
- 컨텍스트와 일지 파일 분리
- Cursor에서 한 모든 작업·추론·결과를 Claude CLI가 파일만 읽고 이어갈 수 있게 정리

### 추론 / 결정
- `CLAUDE_CONTEXT.md`: 변하지 않는 제품·기술 맥락 + 구현 상태 스냅샷
- `WORK_LOG.md`: 시간순 일지 + 열린 이슈 + 다음 액션 (append-only)
- 과거 Cursor 대화 내용을 역사 섹션으로 백필

### 한 일
- `docs/WORK_LOG.md` 생성 (이 파일)
- `docs/CLAUDE_CONTEXT.md`에서 §13 세션 로그 제거, 문서 구조·에이전트 규칙 추가

### 결과
- Claude CLI 시작 시 두 파일만 읽으면 작업 재개 가능한 구조

---

## 2026-07-02 — Cursor — Claude CLI 로그 품질 검토

### 사용자 요청
- Claude가 `CLAUDE_CONTEXT.md` §13에 남긴 로그가 잘 되고 있는지 검토

### 추론 / 결정
- 로그 내용은 **사실과 일치** (git 상태, BKT 버그) — 품질 양호
- 다만 §13에 일지+컨텍스트 혼재 → 파일 분리 권장 (이번에 실행)

### 검증
- `git status`: uncommitted materials→documents, 0009 migration 등 확인
- `service.py:117` + `bkt.py:18`: `strength_init` vs `p_init` 불일치 확인 → **ISSUE-001**

---

## 2026-07-02 — Claude CLI — 컨텍스트 교차검증 + 버그 발견

### 사용자 요청
- (암묵) `CLAUDE_CONTEXT.md` 읽고 프로젝트 동기화

### 한 일
- git 원격·로컬 uncommitted 변경 파악
- 문서 §1~12 vs 코드 교차검증 (게이티드 BKT, bridge/focused, ingestion 등 일치)
- BKT 채점 크래시 버그 발견 → §13에 기록 (후에 WORK_LOG로 이관)

### 열린 이슈
- ISSUE-001 등록

---

## 2026-06-30 전후 — Cursor — 제품 이해·흐름·팀 스키마 논의 (백필)

### 배경
팀원 full SaaS 스키마(~25 테이블) vs 현재 MetaLearn 구현(8→확장) 비교·정렬 작업이 진행됨.

### 사용자가 확정한 제품 철학 (핵심)
1. 개인 교재 PDF → LLM 파싱 → 개념+선수지식 그래프
2. 문제로 수준 파악: A 틀림 → A 모름; **선수도 모르면** A만 가르쳐도 소용없음 → **선수 뼈대 후 A**
3. A 약하지만 선수는 앎 → **교재 본문만**
4. 전원에게 선수 깔지 않음 — **개념마다** 다름
5. 진단 결과 = **씨앗** (사용자×교재 프로필)
6. 씨앗으로 **개념별** JIT 커리큘럼 (`bridge` = 선수+본문, `focused` = 본문만)
7. 학습 중: 까먹음/이해 확인 → 틀리면 **왜 틀렸는지 분석** → 재설명/커리큘럼 재생성 (목표, 미구현)

### 논의·결론 요약

| 주제 | 결론 |
|------|------|
| 팀원 스키마 중 MVP에 과한 것 | 결제, 알림, 4단 CMS, SM-2 등 |
| 정식 출시 기준에서도 MetaLearn과 안 맞는 것 | `serve_variant`, `external_refs`/verified, related/application 엣지, ceiling/floor 진단, push_tokens, JIT 제품에 4단 CMS |
| 동일 엔티티 다른 이름 | materials≈documents, p_known≈strength, concept_prerequisites≈concept_edges 등 |
| rename + 부모 테이블 추가 | 코드 반영 완료, **미커밋** |
| 벡터화 범위 | 개념 name+description만 (전문 청크 RAG 아님) |
| PDF 본문 저장 | `documents.raw_text`에 전체, 개념별 본문 컬럼 없음 |
| 개념 X 커리큘럼 분기 | strength&lt;0.5 → bridge; ≥0.5 → focused; 앎 → 자동 생략·수동 선택 학습 |
| bridge ≠ 선수만 | **선수 챕터 + 본문** 둘 다 |

### Cursor에서 완료한 코드 작업 (미커밋)

**Rename / 정렬**
- `materials` → `documents`, `markdown` → `raw_text`, `material_id` → `course_id`
- `concept_prerequisites` → `concept_edges`, `concept_masteries` → `concept_mastery`, `p_known` → `strength`, `depth` → `depth_level`

**신규**
- `users`, `courses`, `enrollments`, `auth` (default `dev@local`)
- `backend/alembic/versions/0009_team_schema_alignment.py`
- `frontend` documents 페이지, `flowStore` courseId

**삭제**
- `backend/app/features/materials/`, `frontend/features/materials/`

**프론트 라우트**
- `/lab/documents`, `/lab/diagnostic`, `/lab/curriculum`

### 미완 / 블로커
- Docker 미기동 시 `alembic upgrade head` 미실행
- ISSUE-001 BKT 버그 (rename 작업 부산물 추정)
- `seed`, `review` 스텁
- 학습 중 적응 루프 미구현

---

## 2026-06-30 전후 — Cursor — 인프라·문서 작업 (백필)

### 한 일
- DB 초기화·재기동 (`docker compose down -v`, up, alembic)
- MVP DB 스키마(8테이블) 문서화
- `docs/CLAUDE_CONTEXT.md` 최초 작성 (Cursor↔Claude 동기화용)
- 전체 흐름 mermaid 다이어그램 정리

---

## 의사결정 로그 (참고)

| 날짜 | 결정 | 이유 |
|------|------|------|
| 2026-06 | 팀원 스키마 **전체 이식 안 함** | MetaLearn은 JIT+BKT 중심, 4단 CMS·결제 등 제품 루프 밖 |
| 2026-06 | `materials` → `documents` 등 rename | 팀 스키마 1:1 동등 엔티티만 맞춤 |
| 2026-06 | `diagnostic_sessions` 유지 | 팀 스키마 `attempts` 통합은 출시 후보, 당장 교체 안 함 |
| 2026-06 | `curricula.blocks` JSON 유지 | 고정 교재 CMS 대신 JIT |
| 2026-07 | CONTEXT / WORK_LOG 분리 | 일지가 길어져 컨텍스트 오염 방지 |

---

## Git 스냅샷 (마지막 확인: 2026-07-02)

- **브랜치:** `feat/parsing` (= `origin/feat/parsing`, ahead/behind 없음)
- **마지막 커밋:** `33a672d` refactor: 팀 스키마 정렬 (materials→documents) + BKT/커리큘럼 버그 수정
- **uncommitted:** 없음 (working tree clean)
