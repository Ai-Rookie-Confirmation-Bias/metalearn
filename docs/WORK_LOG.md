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
| ISSUE-005 | P2 | open | 학습 중 확인 루프 (서버 채점·오답분석·재설명·재생성). **2026-07-09**: 서버 채점 완성(cloze 빈칸별+LLM 폴백, mcq/reveal), 「풀면 진행」게이트, 정답 공개 — 실 E2E. **2026-07-11 핵심 완결**: `POST /blocks/:id/supplement` — LLM 오답 진단(diagnosis+misconception)+맞춤 재설명 1콜(근거·성향·faithfulness 첫 생성과 동일 원칙, 인용 폴백), 진단은 attempts.meta 영속 → 다음 국소화의 misconception_signal로 배선(dead branch 발화 확인, 오개념 시 선행 삽입 억제), 프론트 자동 fetch+AI튜터 패널 표시 — mcq/explainBack 실 LLM E2E 통과. **남은 것**: AI 튜터 채팅 실동작(mock), `decide_intervention_stage`(hint_ladder) 정리 |
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
| ISSUE-016 | **P1** | ~~closed~~ | **문항 신뢰성 부족** (2026-07-05 사용자 관점 E2E에서 발견, course 24/session 21). ① [심각] mcq 수학 오류 — "y=x³-3x²+1 (2,-3) 접선 기울기" 정답 0이 보기에 없고 "-1"이 정답 마킹. 제대로 계산한 학생이 틀리고 BKT가 오염 ② [심각] 해설에 LLM 자기교정 독백("다시 계산… 문제 오류 가능성…") + 프롬프트 내부 참조("원문 1에서…") 그대로 노출 ③ [중간] 서술 채점 인정 범위 좁음 — 교재 문구("산란")만 정답, 물리적으로 타당한 "분산" 오답 처리 ④ [중간] 표지 지문 유래 노이즈 개념(무지개·물방울) 출제. **원인 분석**: ①②③은 생성 단계 결함(원문 접지는 정상 작동 — 정제 무관), ④만 정제 보수성의 하류 증상(공격적 제거는 본문 손실 위험 → 진단 대상 선정에서 거르는 방안 병행 검토). **대응(착수)**: 해설 정리(프롬프트 규칙+후처리) + 생성 후 문항 검증 패스(mcq 정답 존재·유일·계산 확인, 불합격 재생성). **2026-07-05 구현 완료(`d9f78f3`)**: 원문 근거 주입(출처 청크 발췌 1,500자, 배치는 태그 참조) + 해설 후처리(독백 컷·내부참조 치환·350자) + 검증 패스(검수 LLM my_answer 산출→코드가 대조, 불합격 단건 재생성+1회 재검증). E2E(session 26) 오답 mcq 2건 적발·재생성, 최종 4/4 정확 — ①② 해결로 close. **잔여**: ~~③ 서술 채점 인정 범위~~(**2026-07-13 해결** — 채점 기준을 "정답과 동의어인가"→"이 문항의 답으로 인정 가능한가"(A 의미동등 / B 문맥상 타당한 대안)로 확장, 학습 cloze·진단 심판 양쪽, 실 API E2E 확인) ④ 노이즈 개념 출제(진단 대상 선정 필터) — 별도 후속 |
| ISSUE-017 | **P1** | 구현·검증 | **씨앗 산출물 계약(docs/ii.md) 대응** — 커리큘럼 팀원이 인수인계 계약 제시(2026-07-05). 이미 일치: 에지 방향(from=학습대상→to=선행), 임베딩 halfvec 4096, depth 방향(기초=큰 값), 절↔대표개념 1:1, mastery=BKT p_known. **신규 작업 4**: ① `concepts.key` 영문 슬러그 생성(코스 내 유니크) ② **`external_refs`** ✅ **구현·E2E검증(2026-07-13, 세션20)** — 수집=`seed/refs.py`(한국어 위키 REST + 실패 개념 LLM 폴백, source_kind로 출처 강도 표기, 멱등; 커밋 `582407d`, 07-07). 소비=ai_prereq 절 생성이 근거게이트+faithfulness를 external_ref snippet 기준으로 통과(`generator._verify`/`check_faithfulness`, `service._prepare_generation_input`). **실DB 검증**: ai_prereq 54개 전부 근거 보유(54/54, web 10·llm 44), 'OSI 계층 모델' 절을 실 Solar로 생성 → 사실블록 5개(concept×2·cloze·mcq·explainBack) **전부 verified + external_ref_ids 보유**, analogy 근거면제. **남은 품질**: web 히트율 19%(동음이의·429로 대부분 LLM 폴백=약한 출처) — 검색원 보강 여지(위키 외 소스/재시도) ③ chapters/sections 행 생성이 씨앗 소관(파트→chapters, 대표 개념→sections.concept_id, order 10/20/30 간격, gen_status는 pending 유지) ④ enrollments(floor/ceiling/diag_status/purpose)+concept_mastery 초기 시드(locked/todo/mastered) — ISSUE-015 배치고사 출력 스펙으로 확정. **역제안 2**: 키워드 매칭 대신 `concepts.source_chunk_id` FK 조회(개념명↔원문 문자열 불일치 문제 회피), UUID 전환 시점 합의. **DoD**: 커리큘럼 트리 조회→챕터 generate→전 절 blocks 서빙(verified=true)→attempts 채점, 4종 통과 시 인수인계 완료 |

### 다음 액션 (팀 합의 대기 없음 — 우선순위 제안)

1. 학습 중 확인 루프 (ISSUE-005) — 서버 채점·「풀면 진행」·정답 공개 완료, **LLM 재설명 루프** 남음(§2.5)
2. 팀 계약(ii.md, ISSUE-017) — floor/ceiling 의미 축소 합의 + external_refs 후속
3. `redesign/diagnostic-profiling` → dev 머지 (팀 합의 후)

---

## 2026-07-14 (세션25) — Claude CLI — 페어 학습 구조: 조각+확인문제 연계 배치 (설명 몰빵 → 인터리브)

### 사용자 요청
- "구조화 박스1+문제1 / 박스2+문제2처럼 연계 문제가 바로바로 나오는 게 좋겠다" → 채택·구현.

### 추론 / 결정
- **연계형 채택 근거**: ① 텍스트 벽의 잔여(설명 3~4블록 연속 수동 읽기) 해소 ② 오답 신호(국소화→재설명)가 조각 단위로 조기 발화 ③ 제안서 원리 ②("역질문이 콘텐츠에 박힘") 정합. **너무 쉬운 즉시 인출** 우려는 역할 분담으로 흡수 — 페어 문제=가벼운 확인(cloze/mcq), 절 끝 explainBack=통합 인출, 장기기억=복습(SM-2).
- **프롬프트만으론 순서 불이행**(실측: concept 5연속, 페어 무시) → **결정적 재배열**: 확인 문제에 `afterConcept`(몇 번째 조각의 확인인지, 1부터) 태그를 받게 하고, 코드(`order_interleaved`)가 배치를 강제. 태그 없는 문제=설명 뒤(기존 배치), 범위 초과 태그=마지막 조각 흡수, explainBack=항상 맨 뒤. "문제 근거는 앞의 설명" 규칙을 배치가 깨지 않는 설계.

### 한 일 (generator.py + mock.py, 프론트 변경 0)
- build_prompt 구성 원칙 교체: "설명 먼저→인출 나중" → "조각으로 가르치고 조각마다 꺼내게 한다"(조각 1~3개, 각 조각 확인 문제 + afterConcept, 보조 자료는 관련 조각 옆, 마지막 explainBack 고정).
- `order_interleaved()` 순수 함수 + 생성 파이프라인 마지막 단계로 적용, meta.order 재스탬프. afterConcept는 meta로만 저장(serializer BlockMeta가 안 실어 와이어 불변 — 계약 변경 0).

### 검증
- 단위: 몰빵 응답(concept×3 뒤 문제 몰빵) → `concept·table→cloze / concept·analogy→mcq / concept→(초과태그 흡수)` 정확 재배열 + order 재스탬프 ✅
- 실 Solar: `concept → cloze(1) → concept → cloze(2) → explainBack` — 목표 구조 그대로 ✅ (다른 샘플은 확인 문제가 품질 게이트에서 폐기돼 조각만 남음 — 게이트 정상 동작, 배치 로직 무관)
- mock 회귀: explainBack 맨 뒤 유지 ✅

### 다음 액션
1. 확인 문제 폐기율 관찰 — 페어가 자주 비면 "폐기 시 해당 조각 확인 문제 1회 재생성" 후속 검토.
2. (기존) 튜터 톤 다듬기 · Layer 2 조사 · 1블록 절 실태 파악.

---

## 2026-07-14 (세션24) — Claude CLI — AI 튜터 채팅(FAB화) + 코스 삭제 + 코스별 라우팅 + 트라이얼 포트

### 사용자 요청
1. 학습 화면에서 코스 여러 개일 때 courses[0]만 보는 문제 해결.
2. AI 튜터 채팅 구현(전에 구 세션 아키텍처에 있다 v2 재구축 때 제거된 335줄 tutor.py 확인) + **우측 고정 패널 → 우하단 FAB 토글로**: "학습 칸이 좁고, 튜터를 많이 쓰면 서비스 목적(인출)에 안 좋다".
3. 책장에서 코스 삭제.
4. (버그) library 빈 화면 + "업로드 실패: Network Error".

### 추론 / 결정
- **튜터 = 정답 자판기 방지 설계**: 서버 프롬프트가 ① 절 근거 접지(발췌 밖 지어내기 금지) ② **정답 비유출**(퀴즈 정답 직접 요구 시 단계적 힌트·역질문) 강제 — `tutor.py` 순수 계층. 대화는 서버 무저장(history 왕복, supplement의 비영속 원칙). UI도 같은 철학: 항상 떠 있지 않고 **FAB 토글**, supplement 도착 시 알림 점만.
- **Network Error 원인 = Windows(Hyper-V) excludedportrange**: `wsl --shutdown` 후 57981–58080 대역이 예약돼 브라우저→localhost:58001만 거부(**WSL 내부 curl은 정상이라 은폐**). 트라이얼 backend 포트 58001→**48001**(<49152, 재발 불가)로 이동.
- **코스 삭제**: NO ACTION FK는 PG에서 **즉시 검사**(DEFERRABLE 아님)라 CASCADE에 못 맡김(ORM·Core 단문 모두 FK 위반 실측) → 역순 명시 삭제: 학습이력(attempts·mastery·progress·enrollment·cursor) → chapters(→sections→blocks) → courses(→concepts·documents) → legacy 1:1 document 고아 정리.

### 한 일
- 라우팅: `/learning/:courseId` + 책장 링크 코스별 + 코스 전환 시 절 선택·신호 리셋(remount 없음 대응) — 이슈 #4 해결 (`7c62754`).
- 트라이얼 포트 48001 (`ffd6888`) + 메모리/주석에 excludedportrange 함정 기록.
- 튜터 채팅: `tutor.py`(신규) + `POST /tutor/chat` + 프론트 `tutorChat.ts`·AiTutorPanel 채팅 배선(Enter, IME 조합 가드, 절 변경 리셋, 자동 스크롤) + LearningPage FAB·플로팅 패널·unread 점. 고정 340px 사이드바 제거 → 본문 폭 확대.
- 코스 삭제: `DELETE /courses/:id`(소유자만, `delete_course_deep`) + 책장 카드 호버 휴지통(confirm 후 실행, 생성 중 드래프트 제외) + 목록 invalidate.

### 검증 (실 스택·실 Solar)
- 튜터: 개념 질문 → 근거 접지+성향 반영 답변 ✅ / **"정답 그냥 알려줘" → 정답 단어 없이 소크라틱 역질문으로 유도** ✅
- 코스 삭제: NO ACTION 전 경로(attempts·mastery·progress·enroll·cursor·blocks·concepts·documents) 커버한 합성 코스로 204 + 잔여 0행 ✅ / 타 유저 삭제 시도 404(소유권 가드) ✅
- Windows에서 backend(48001)·frontend(55173) 모두 200, tsc 0, backend import 클린.

### 다음 액션
1. 실 코스에서 table/diagram/구조화 concept + 튜터 FAB 육안 확인(사용자).
2. 튜터 응답 톤 다듬기("이 절의 범위를 벗어난다" 직역투 — 프롬프트 문구 조정 후보).
3. Layer 2 조사(Document Parse figure 좌표) + 기존 "1블록 절" 실태 파악(세션23 잔여).

---

## 2026-07-14 (세션23) — Claude CLI — Layer 1: diagram(Mermaid) 블록 + LLM 응답 붕괴 버그 발굴·수리

### 사용자 요청
- Layer 1(Mermaid) 구현 승인 — 렌더 검증 게이트 설계 확정 후 착수. 절대 원칙 유지(프론트=조립만).
- 구현 후 검증 + **스택 구동**(사용자 직접 확인 예정).

### 추론 / 결정 (설계 핵심)
- **LLM에게 Mermaid 코드를 직접 쓰게 하지 않는다** — 그래프 JSON(nodes/edges)만 받고 서버가 결정적으로 조립(`diagram.assemble_mermaid`) → 문법 오류가 구조적으로 불가능, `click`·`%%{init}%%` 인젝션도 조립기가 안 만들므로 원천 차단. v1은 flowchart 단일(TD/LR).
- 그래프 정합성 게이트는 `DiagramData` 검증기: 치명(dangling 참조·id 중복·id 패턴)=폐기, 사소(자기 루프·고립 노드)=제거 후 통과 — table 행 패딩과 같은 관대 철학.
- faithfulness는 **엣지 문장화**("A → B (라벨)")로 기존 `check_faithfulness` 재사용 — 다이어그램 환각은 노드가 아니라 화살표(없는 관계 주장)에서 나온다.
- 프론트는 2차 방어선(mermaid.parse) + 렌더 실패 시 nodes/edges **구조화 폴백 리스트**(빈 화면 금지). mermaid.js는 dynamic import(번들 lazy), `securityLevel:"strict"`.

### 한 일
- 백엔드: `DiagramData/DiagramNode/DiagramEdge`(schemas), **`diagram.py` 신설**(조립+문장화), generator 등록(_TYPE_SPECS/_FAITHFULNESS_TYPES/_block_claim_text/프롬프트/cloze 컨텍스트), mock diagram 응답.
- 프론트: `DiagramBlock.tsx` 신설(lazy mermaid + parse 2차 방어 + 폴백), types/registry 등록, **mermaid@11.16.0 추가**(pnpm, 컨테이너 스토어 이슈는 `--store-dir`로 해결).
- **[중요] 기존 잠복 버그 발굴·수리**: solar-pro3(json_mode)가 블록 객체 사이 닫는 `}`를 간헐 누락 → 여러 블록의 키가 한 객체로 합쳐지고 JSON은 유효(중복 키 허용)라 **표준 파싱이 마지막 블록만 남김**(6블록→1블록 조용한 증발, 에러 0). 실측 재현율 ~절반. 수리: `parse_llm_blocks`에 ① 중복 키 분리 hook(`_dup_key_splitting_hook` — 키 반복 지점마다 조각 분리) ② 블록 모양({type,data}) 재귀 수집(blocks 배열 밖 유출 방어) ③ data 기준 중복 제거 ④ 3블록 미만이면 재생성+최선 시도 유지. **Layer 0 이전부터 있던 버그로 추정 — 기존 코스의 빈약한 절들 원인일 가능성.**

### 검증
- 게이트 단위: dangling/중복 id/자기 루프만·1열 표 폐기, 고립 노드·자기 루프 관대 제거, 라벨 이스케이프, LLM이 넣은 mermaid 키 무시(항상 서버 조립본) ✅
- 파서 회귀: 실패 raw 실물에서 **7블록 전부 복원**(concept/table/diagram/analogy/cloze/mcq/explainBack), 정상 응답 회귀 무손상 ✅
- faithfulness 부정 테스트: 지어낸 화살표("물리→응용 암호화 전달") → supported:false 폐기 ✅
- **실 Solar 3/3 샘플 안정**: 매회 6블록 + OSI 캡슐화 5계층 flowchart(TD, 라벨 엣지) 정확 생성 ✅ (수리 전: 절반이 1블록 붕괴)
- 프론트 tsc 0, 스택 재기동 클린(backend/frontend 200). 주의: 이전 asyncio.run 2회 테스트 스크립트는 solar 커넥션 풀이 닫힌 루프에 물려 오탐 — 단일 루프에서 테스트할 것.

### 다음 액션
1. 실 코스에서 신규 챕터 generate → table/diagram/구조화 concept 육안 확인(기존 저장 블록엔 소급 안 됨).
2. Layer 2 조사: Document Parse figure 좌표 → 원문 이미지 크롭 재사용.
3. 기존 코스 중 "1블록 절" 실태 파악(파서 버그 소급 영향) — 재생성 대상 선별.

---

## 2026-07-14 (세션22) — Claude CLI — 학습 콘텐츠 시각 구조화 Layer 0: concept 구조화 박스 + 비교표(table) 블록

### 사용자 요청
- 텍스트만으로는 학습 환경이 지루함 → 박스 분리·시각 자료로 이해도를 높이자. 비용 대비 효과 4층 정리 중 **Layer 0(구조화 텍스트) 착수 승인**.
- **절대 원칙 재확인: 프론트는 조립만, 백+DB가 구조화 JSON만 보낸다** (LLM HTML 생성 금지).

### 추론 / 결정
- 봉투+registry 설계 덕에 "새 유형 = data 모델 + 렌더러"로 끝난다 — 마이그레이션 0(blocks.type은 String(64) 자유형), 계약 변경도 additive라 팀 충돌 없음.
- 발견: 백엔드는 `whyItMatters`를 이미 생성하는데 **프론트가 버리고 있었음**(types.ts에 필드 없음) → 구조화 렌더로 회수.
- table 행 정렬은 관대 처리(초과 절단·부족 공백 패딩) — LLM 정렬 실수로 표 전체를 폐기하지 않기 위해. 내용 정확성은 faithfulness 게이트가 담당(table도 대조 대상에 포함).

### 한 일
- **백엔드**: `ConceptData`에 `example`/`misconception` 추가, `TableData` 신설(columns≥2, rows≥1, 행 정렬 validator) — `schemas.py`. `_TYPE_SPECS`/`_FAITHFULNESS_TYPES`에 table 등록, `_block_claim_text` table 지원, cloze 풀이검증 컨텍스트에 table 포함, `build_prompt` 확장(구조화 필드 지침 + "근거에 비교 대상이 있을 때만 table") — `generator.py`. mock LLM에 example/misconception+table 응답 추가 — `mock.py`.
- **프론트**: `ConceptBlockData` 확장 + `TableBlockData` 신설 — `types.ts`. ConceptBlock 구조화 콜아웃 렌더(왜 중요할까=indigo·예시=green·흔한 오해=amber, 좌측보더 idiom) — `ConceptBlock.tsx`. `TableBlock.tsx` 신설(overflow-x-auto, 첫 열 강조, 줄무늬, caption). registry에 `table` 케이스.
- serializer 스트립 불필요(concept/table엔 정답류 없음 — data 원본 그대로 서빙이 정상).

### 검증
- pydantic 단위: 행 절단/패딩, camelCase 왕복, 1열 표 거부 ✅ (컨테이너 py3.12)
- 파이프라인(mock LLM, 게이트 전부): `['concept','table','analogy','cloze','mcq','explainBack']`, table tracked=False·verified=True, concept에 example/misconception 보존, strip_answers 무손실 ✅
- **실 Solar 라이브**: LAN/MAN/WAN 근거로 생성 → concept 5필드 전부 + 4열×3행 비교표(구분/커버범위/속도/오류율) faithfulness 통과 ✅
- 프론트 tsc 0에러(컨테이너), backend/frontend HTTP 200. 스택: mlv2를 이번 세션부터 **`~/metalearn-work` 마운트**로 운용.

### 다음 액션
1. Layer 1: Mermaid diagram 블록(+렌더 가능성 검증 게이트) — "텍스트→도식 자동 생성" 데모 장면.
2. 조사: Upstage Document Parse가 figure 좌표를 주는지 → 되면 Layer 2(원문 이미지 크롭 재사용).
3. 실 코스에서 새 블록 육안 확인(신규 챕터 generate 필요 — 기존 저장 블록엔 소급 안 됨).

---

## 2026-07-13 (세션21) — Claude CLI — feat/purpose-policy 통합 머지 + 백업 푸시 + 라이브 스모크

### 사용자 요청
- `feat/purpose-policy`(소민섭) 변경 확인 → **우리 `feat/yoonhs-work`로 전부 머지**(E2E는 미실시). 이어 리뷰 피드백 반영: ① 로컬만 ahead인 work 브랜치 **백업 푸시** ② 기능 덩어리(purpose+링크+채점개선)라 **integration 머지 + 스택 리로드 + 스모크** 풀 진행.

### 추론 / 결정
- purpose-policy는 우리와 같은 지점(`2ecd6bd`)에서 분기 + 우리 작업(재설명·이유라벨·ingest)을 이미 자기 브랜치로 머지 → **가산적**. work로 머지 시 코드 전부 자동 병합, 충돌은 `docs/WORK_LOG.md` 1개(이슈표·세션블록). 그쪽 ISSUE-016(③해결) + 내 ISSUE-017(external_refs), 세션블록은 양쪽 보존으로 결정론적 해소.
- integration은 `2ecd6bd` → work(`8983939`)의 조상이라 **FF**. 머지 범위에 **새 alembic 마이그레이션 없음**(purpose는 기존 `enrollments.purpose` 소비) → 스택은 컨테이너 재시작만으로 반영(마운트=`~/metalearn-placement/backend`).

### 한 일
- `feat/yoonhs-work` ← `origin/feat/purpose-policy` 머지(`8983939`), WORK_LOG 충돌 결정론 해소(스크립트).
- 백업 푸시: `origin/feat/yoonhs-work` `2ecd6bd..8983939`(FF, 0/0 동기화).
- integration FF: `feat/yoonhs-integration` → `8983939`, `origin` 푸시(0/0).
- 스택 리로드: `mlv2-backend-1`·`mlv2-frontend-1` 재시작 → 클린 기동(Application startup complete, import 에러 0), backend/frontend HTTP 200.
- 라이브 스모크 3종(실 Solar·실 스택).

### 변경 파일
- 코드: purpose-policy 편입분(`learning/policy.py` 신규, `documents/linkfetch.py` 신규, `learning/{generator,service,grading}.py`, `diagnostic/*`, 프론트 `Prose.tsx` 등 25파일) — 전부 그쪽 커밋, 우리 쪽 신규 편집 없음.
- `docs/WORK_LOG.md`(본 블록 + 충돌 해소).

### 결과
- 통합본 = purpose 정책 + STEP2 링크 RAG + 서답형 채점 관용도(ISSUE-016③) + 우리 external_refs·재설명·이유라벨, 라이브 무회귀 확인.

### 검증 (라이브 스모크, mlv2 통합 스택)
- **서답형 채점 관용도(ISSUE-016③)**: 프로토콜 3요소 cloze에 영문표기 `[Syntax,Semantics,Timing]`(정답 `구문(Syntax)/의미(Semantics)/타이밍(Timing)`) → `correct:true`, `blankResults:[T,T,T]` — 표기차 인정 ✅
- **재설명 루프 회귀(ISSUE-005)**: cloze 오답(`바나나`) → `correct:false` → `POST /blocks/:id/supplement` → 오답 진단+`misconception:true`+맞춤 재설명(`fallback:false`, 실 LLM) ✅
- **purpose 분기**: 정책 4갈래 라이브 분기(exam tracked/cap8/sm2 0.7 · hobby tracked=False/cap0), 실 exam enrollment→생성입력에 시험 지시문+tracked=True, hobby로 뒤집으면 tracked=False(읽기전용 롤백) ✅
- 기동: backend 클린(startup complete, 에러 0)·HTTP 200 / frontend 200. 정적: 백엔드 AST 문법 0에러.
- 스모크 부수효과: dev 유저(00..01) attempts 2건 기록(cloze 정/오답) — dev DB 잔여, 무해.

### 다음 액션
1. external_refs 검색원 보강(위키 히트율 19%) — 세션20 잔여.
2. purpose 분기의 **생성 산출물** 관찰(exam vs hobby 실제 블록 밀도·tracked 차이) — 정책→생성 결과까지 육안 확인은 미실시.
3. dev 머지(팀 합의) — integration 최신은 `8983939`.

---

## 2026-07-13 (세션20) — Claude CLI — ISSUE-017 ② external_refs 소비 경로 E2E 검증 (코드 변경 없음, 검증·정합)

### 사용자 요청
- 저번 세션 이어서 진행. 작업 브랜치 `feat/yoonhs-work` 확인 → 다음 액션 중 **external_refs(ISSUE-017 ②)** 스레드 선택.

### 추론 / 결정 (왜 이렇게 했나)
- 착수 전 조사에서 **코드-이슈표 불일치** 발견: 이슈표·07-11 다음액션은 "external_refs 수집 방식 미정(웹 vs LLM)"으로 open이었으나, 실제로는 `seed/refs.py`(위키 REST + LLM 폴백)가 커밋 `582407d`(07-07, assembly-v2 UUID 포팅)에 **이미 구현**돼 있었고 CLAUDE_CONTEXT도 완료로 기재. → 남은 일은 신규 구현이 아니라 **E2E 검증 후 정합**으로 판단.
- 실DB 조사에서 진짜 갭 발견: 수집은 100% 됐으나(ai_prereq 54/54) **ai_prereq 개념이 어떤 절에도 연결된 적이 없어**(전 절 45개가 book, `[선행]` 챕터 2개도 book 개념 통신·데이터 기반) `ai_prereq → external_refs → verified 블록` **소비 경로가 한 번도 안 돌았음**. 메모리 규칙(실검증 없이 closed 금지)상 이 경로를 실제로 태워야 함.
- 공유 dev DB를 오염시키지 않도록, 프로덕션 함수(`_prepare_generation_input` → `generate_section_blocks`)를 **읽기 전용(rollback)** 스크립트로 실 Solar·실 external_ref 데이터에 직접 태워 검증.

### 한 일
- 실DB 카운트 확인: courses 4 / ai_prereq 54 / book 377 / external_refs 54(web 10·llm 44) — **ai_prereq 54개 전부 근거 보유(커버리지 100%)**.
- 소비 배선 정독: `service._prepare_generation_input`(concept.source==ai_prereq → `get_concept_external_refs` 로딩), `generator._verify`(ai_prereq는 external_ref_ids 필수), `check_faithfulness`(external_ref snippet 기준 대조), `serializer`(🤖 인용 배지).
- E2E 검증 스크립트로 'OSI 계층 모델'(ai_prereq, web ref) 절을 실제 생성 경로에 태움(컨테이너 내 실행 후 스크립트 제거, DB 미변경).

### 변경 파일
- `docs/WORK_LOG.md` (본 블록 + ISSUE-017 ② 상태 open→구현·검증) — **제품 코드 변경 없음**.

### 결과
- ISSUE-017 ② = 수집·소비 **양방향 실증 완료**. 이슈표 정합(open→구현·검증). "수집 방식 미정"은 stale였음을 확인·해소.

### 검증 (실행한 명령·결과)
- 실DB(psql): ai_prereq 54/54 external_refs 보유(web 10/llm 44) ✅
- 실 Solar E2E(읽기전용, mlv2-backend-1): 'OSI 계층 모델' 절 → external_ref 1건 로딩 → 블록 6개 생성 → **사실블록 5개(concept×2·cloze·mcq·explainBack) 전부 `verified=True` + `external_ref_ids` 보유**, analogy 1개 근거면제 통과. 근거게이트+faithfulness 모두 external_ref snippet 기준 통과 → **PASS** ✅

### 열린 이슈 (남은 것)
- [ ] external_refs 품질: web 히트율 19%(10/54) — 위키 동음이의·429로 대부분 LLM 폴백(약한 출처). 검색원 보강(위키 외 소스·재시도·개념명 정규화) 여지.
- [ ] 소비 경로의 **자연 발화** 검증: 실 학습 플로우에서 localization이 ai_prereq 개념을 blame → `insert_prerequisite_chapter`로 절 생성되는 케이스는 아직 미발생(현 DB의 `[선행]` 챕터는 book 개념). 그래프 엣지가 ai_prereq를 선수로 가리키는 코스에서 재확인 필요.

### 다음 액션
1. (선택) external_refs 검색원 보강 — 위키 미스 개념의 web 출처 확보율 개선.
2. ISSUE-017 전체 DoD(트리→generate→서빙→채점 4종)와 dev 머지 — 팀 합의 항목.
3. 저번 세션 홀드 항목(AI 튜터 채팅 실동작) 팀 상황 해제 시 착수.

---

## 2026-07-13 — Claude CLI — 서답형 채점 인정 범위 확장: 동의어·이중 정답이 오답 처리되던 문제

### 사용자 요청
- 서답형에서 "의미는 같고 말만 다른 답"과 "이중 정답(문맥상 똑같이 성립하는 다른 답)"이 그냥 틀렸다고 나옴 — 최선의 수정 방법을 판단해서 고칠 것.

### 추론 / 결정
- 원인: 채점 LLM의 판정 기준이 **"학습자 답이 (유일한) 출제 정답과 의미상 같은가"** 뿐 — 동의어는 심판 재량에 따라 탈락하고, 타당한 대안 답(이중 정답)은 기준 자체에 없어 무조건 오답. 생성 게이트(2026-07-12(2))가 이중 정답 문항을 줄이긴 하지만 구조적 잔여("허가받지 않은 ___")가 실재 → **잔여 문항 결함의 비용을 학습자가 지지 않도록 채점 기준을 "이 빈칸/문항의 답으로 인정 가능한가"로 확장**이 옳다고 판단(BKT 오염 방지 관점에서도 동일 — 타당한 답을 낸 학습자는 아는 것).
- 인정 2원칙: A) 정답과 의미 동등(표기·어순·동의어·수식 표기) B) 정답과 달라도 문맥상 사실적으로 옳고 자연스럽게 성립. 오답 가드: 공허답('것'·'방법') 명시 배제. 경계 사례는 학습자에게 유리하게(1차 실측에서 '사용'이 보수 판정으로 탈락 → 이 규칙 추가 후 통과).
- 학습(cloze LLM 폴백)과 진단(자유서술 심판)이 같은 결함 구조라 둘 다 수정. explainBack 루브릭에도 "교재 문구 그대로일 필요 없음(동의어·자기말·타당한 다른 예시 인정)" 명시.

### 변경 파일
- `backend/app/features/learning/grading.py` — `grade_cloze_llm_blanks` 프롬프트·시스템(A/B 기준+공허답 가드+경계 관대), `_rubric_prompt`(의미 충족이면 O)
- `backend/app/features/diagnostic/service.py` — `_judge_prompt`·`_JUDGE_SYSTEM` 동일 확장

### 검증 (실 mlv2 Docker + 실 Solar)
- 직접 함수 9케이스 전부 PASS: 이중정답(접근/열람·접근/사용) 인정, 패러프레이즈·수식 표기차이 인정, 다른 개념·공허답('것')은 여전히 오답, 진단 심판 3케이스(자기말 풀어쓰기 O / 대안 답 O / 핵심 불일치 X)
- **실 API E2E**(`POST /api/attempts`, 실제 결함 블록 4d53d0f0 "허가받지 않은 ___"→'접근'): '사용' true / '열람' true / '백신 설치' false — 전 경로 확인
- 부수 발견: **uvicorn `--reload`가 Windows 바인드 마운트 변경을 감지 못함** — 코드 수정 후 API가 구버전으로 응답(직접 함수와 판정 불일치로 발각), `docker restart mlv2-backend-1` 후 정상. 백엔드 수정 시 재시작 필요

### 열린 이슈
- [ ] uvicorn --reload 미작동(Windows 바인드 마운트) — `--reload-dir` 폴링 옵션 또는 "수정 후 backend 재시작" 운영 수칙 필요
- [ ] LLM 심판 판정의 비결정성(경계 사례 흔들림)은 프롬프트로 완화했으나 잔존 — 필요 시 생성 단계에서 acceptable_answers를 blanks에 영속하는 방안
- 워킹트리에 `profile/__init__.py` 빈 줄 1개 diff 잔존(이전 끊긴 세션 흔적, 무의미) — 커밋 시 제외/정리 판단 필요

---

## 2026-07-12(3) — Claude CLI — 사용자 관점 풀 여정 E2E: 빈 챕터 무한실패 버그 수정 + mcq 이중라벨 수정

### 사용자 요청
- "사용자 입장으로 테스트해보고 검증해줘" — 신규 코스로 위저드(PDF+링크+시험목적)→온보딩→학습→풀이·오답·재설명까지 전 여정.

### 여정 결과 (course f38ebba1, 사용자 화면 그대로 평가)
- 위저드→ready→온보딩(성향4+프로브+퀴즈6, 문항·정답공개 확인)→프로필 "비유로 이해하는 맥락형 실전가"·갭3·시딩21 ✓
- 학습: 자동생성→서빙. 설명 문단 4개(가독성 반영)·은행금고 비유·mcq 구분훈련형(시험 목적 반영)·**정답 유출 검사 깨끗**(blanks/answerIndex/rubric 전부 스트립) ✓
- 풀이: 정답→해설 / 오답→정답공개+`nextAction=supplement`→AI튜터 진단("사람을 자연적 위협으로 오해")+맞춤 재설명 / 서술 1.0점+코멘트 / 오답 포함 전부 시도→completed(풀면 진행) ✓

### 발견·수정한 버그 2건
- **[P1·수정] 빈 챕터 무한 실패**: 씨앗 트리가 절 0개 챕터를 만들면(이번 코스 11챕터 중 6개!) `run_chapter_generation`이 total=0→**조용히 FAILED**(예외·로그 없음, gather return_exceptions까지 겹쳐 원인 은폐) → 사용자는 「다시 생성→또 실패」 무한 막힘. **수정**: 생성 대상 절 0 + 복습 0이면 ready 통과(만들 게 없는 건 실패가 아님) — 재현·수정·검증(빈 챕터 즉시 ready)
- **[UX·수정] mcq 선지 이중 라벨**: LLM이 선지 텍스트에 자체 라벨 포함("A. 내부 직원…")→UI 라벨과 겹쳐 "A) A. …" 표시 → `_coerce_block`에서 선지 앞 라벨 정규식 스트립, 단위 검증

### 열린 이슈 (신규 발견)
- [ ] **씨앗 트리 비결정성**: 같은 PDF인데 실행마다 챕터 구조가 다름 — 이번 코스는 "✓" 접두사 챕터·"기밀성" 챕터 중복 2개·빈 챕터 6/11 (이전 동일 PDF 코스는 정상 4챕터). 추출·파트 판정 LLM 비결정성 — 빈 챕터 억제/병합·제목 정규화(✓ 등 마커 제거) 필요
- [ ] 진단(온보딩) 문항엔 새 품질 게이트 미적용(learning만) — "변환하는 ___의 한 방법"→'기술' 같은 애매 문항 잔존, diagnostic 생성에도 확장 후보
- [ ] explainBack "2가지 관점" 임의 개수 강제 잔존(경미)

---

## 2026-07-12(2) — Claude CLI — 서답형 품질 개선: 출제원칙(IWF) + Generate-then-Validate cloze 풀이검증 + 결정적 결함 검사

### 사용자 요청
- 서답형(빈칸·서술) 문제가 이상함 — 직접 보고 원인·해결방안 제시(타 에듀테크 LLM 출제 방식 조사 포함) → 1+2단계 그대로 진행.

### 진단 (실 DB 문항 실물 분석)
결함 5종 실증: ① **정답 비유일**("허가받지 않은 ___"→'접근'만 정답인데 사용·열람도 성립, "___를 고려"→'전문적 지식'은 사실상 못 맞힘) ② **자기참조**(문장 안에 정답 그대로: "정보통신망 이용 범죄는 ___을 통해"→정답 '정보통신망') ③ **힌트가 정답 노출** ④ 임의 명사 빈칸·같은 답 2빈칸·비문 ⑤ explainBack **문항-루브릭 불일치**(안 물은 것 채점)+한 문항 과적재. 원인: 생성 프롬프트에 출제 원칙 전무 + 검증 게이트가 사실성(faithfulness)만 봄 — **"풀리는 문제인가"는 아무도 안 봄**(진단 mcq만 ISSUE-016 풀이검증 있음).

### 업계 조사
Generate-then-Validate(과생성→검증 필터, 5개 건지려면 15개 생성이 실측 정상), IWF(Item-Writing Flaws) 루브릭 자동검증(SAQUET/GPT-4), cloze는 단서(cueing) 금지·통사 적합이 표준. 결론: 프롬프트 규칙(불량률↓) + 검수 LLM 직접 풀이(잔여 불량 차단) 2중 구조가 업계 정석.

### 한 일 (`learning/generator.py`)
- **[1단계] `_ITEM_RULES`** 출제 원칙 5조를 build_prompt·_retrieval_prompt에 주입(정답 유일·자기참조 금지·힌트 정답 금지·핵심 용어만·1문항 1과제/루브릭 정합)
- **[2단계] `verify_cloze_drafts`** — 검수 LLM이 '학습자 상황' 재현: 정답 모른 채 설명(concept/analogy) 텍스트만 보고 빈칸 풀이 + **alternatives 적극 나열**(의미 다른 대안 발견 시 결함) → 코드가 `_answers_match`(정규화+공백무시, 채점보다 관대)로 대조, ambiguous/실질 대안/불일치 → 폐기. 절당 배치 1콜, LLM 실패는 관대 통과(faithfulness 동일 정책). learn·review 두 경로 공용(`_drop_unsolvable_cloze`)
- **[3a] `check_cloze_deterministic`** — E2E에서 검수 LLM이 놓친 자기참조("…{{blank}}은 …인데, 금융 정보가 **변조**될 경우"→정답 '변조'가 본문에 등장 — 검수는 '잘 풀림'으로 오판) 발견 → **코드 결정적 검사**로 차단: 자기참조=폐기, 힌트 정답 노출=힌트만 소거(문항 보존)

### 결과 / 검증 (스텁 LLM 단위 + 실 Solar E2E 3회)
- 단위: 일치=통과/검수오답=폐기/복수답=폐기/실질대안=폐기/표기차이=통과/LLM실패=관대통과/자기참조=폐기/힌트노출=소거 — 전 분기 PASS(실물 결함 사례 그대로 사용)
- E2E: 재생성 문항에서 자기참조·힌트 정답 노출 소멸(힌트 소거 발화 확인), 정의→용어형 양질 문항 위주로 생성
- **잔여 한계(정직 기록)**: 원문 표현 그대로의 애매 빈칸("허가받지 않은 ___"→'접근')은 검수 LLM도 같은 원문을 보고 같은 답을 확신해 통과 — 유일성 검증의 구조적 한계. 후속 후보: 무맥락 풀이(설명 없이 풀게 해 답 확산도 측정), explainBack 루브릭 앵커링(3단계 보류분)

---

## 2026-07-12 — Claude CLI — 커리큘럼 자동 생성(버튼 제거)+자동 갱신 / 몰입뷰어 계보 규명 / 텍스트 가독성(문단·keep-all) / DB 완전 초기화

### 사용자 요청
- ① 학습 진입 시 「생성하기」 버튼 없이 자동 생성 + 완료 시 자동 새로고침 ② 몰입뷰어가 "아는 모습과 많이 달라짐" — dev와 비교 ③ 컨테이너 정리 후 재기동 → 라이브러리 데이터 완전 삭제.

### 추론 / 결정
- **몰입뷰어 계보 규명**: dev엔 학습 화면이 사실상 없음(LearningPage 11줄 스텁 + TutorPanel 23줄 프로토타입, '몰입' 0건). 사용자가 아는 화면 = `feat/front-learning`(프론트 팀원 디자인 원형, mock 171줄 — 몰입뷰어 버튼은 "자리만") → full-assembly-v2(실 API) → `b7e2706`(몰입 토글 실동작) → yoonhs 최신(재설명 버블·이유 라벨)로 누적 진화한 것. **코드 회귀·훼손 없음** — 디자인 뼈대(3컬럼·헤더·게이트 문구)는 원형 유지, 낯선 요소는 전부 후속 기능. 그중 가장 이질적이던 "생성 버튼+수동 새로고침"을 ①로 제거.
- **자동 생성 설계**: 기존 프리페치(ref, 챕터당 1회, 멱등 API)와 같은 패턴으로 현재 챕터 pending 시 자동 트리거 + `waitingGeneration`(pending/generating & 블록 0) 동안 5초 폴링으로 courseTree·sectionBlocks invalidate — ready 되면 화면 스스로 갱신. UI는 스피너+"완성되면 자동으로 열려요", **failed일 때만** 「다시 생성하기」 노출.
- DB 초기화는 볼륨 삭제(`down -v`) + 빈 DB 마이그레이션 0020 재적용. 컨테이너/볼륨 구분을 사용자에게 설명 후 완전삭제 선택받음.

### 한 일 / 변경 파일
- `frontend/src/pages/LearningPage.tsx`: pending 자동 트리거 useEffect + 5초 폴링 useEffect + 생성 대기 UI 교체(버튼·수동 새로고침 제거, failed 재시도만 유지, dead code `refetchBlocks` 삭제)
- **텍스트 가독성**(사용자: "줄바꿈이 안 돼 보기 힘듦") 3층 대응: ① 전역 CSS `word-break: keep-all + overflow-wrap`(한국어 단어 중간 꺾임 방지, `app/index.css`) ② `shared/ui/Prose.tsx` 신규 — \n\n 문단·\n 줄바꿈·**볼드**·\`코드\` 렌더, ConceptBlock(기존 인라인 파서 대체)/AnalogyBlock에 적용 + McqBlock 해설·ExplainBack 피드백·AiTutorPanel 재설명 버블에 `whitespace-pre-wrap break-keep` ③ `generator.build_prompt`에 "body는 2~3문장마다 빈 줄로 문단 구분" 지시 — 신규 생성분부터 문단 생성
- 인프라: mlv2·구스택 잔재 컨테이너 전부 제거, `mlv2_pgdata` 볼륨 삭제 → 재기동 + `alembic upgrade head`(0020) — courses 0·users 0 확인

### 결과 / 검증 (실 mlv2, 새 코스 8d722d67 — 컴윤10 업로드+온보딩 exam 완주)
- 프론트 훅 계약 시퀀스 전체 실검증: pending 진입 → 자동 트리거(연속 2회 멱등 OK) → 5초 폴링 4회 만에 `generating→ready` → 절 블록 8개 자동 서빙 — **버튼·수동 새로고침 없이 완주**. tsc 0
- 순서대로 학습하면 기존 다음-챕터 프리페치가 항상 앞서 생성하므로 대기 화면 자체를 거의 안 봄
- 가독성: 새 프롬프트로 챕터 실생성 → concept body가 **문단 4개(\n\n)** 로 생성됨 확인, tsc 0 — Prose가 <p> 간격으로 렌더(기존 무개행 콘텐츠는 문단 1개로 무해)

### 열린 이슈
- [ ] 몰입뷰어 "낯섦"의 잔여 = 신기능 UI(이유 배지/배너·AI튜터 재설명 버블·선행 배너) — 사용자가 특정 요소를 지목하면 개별 조정
- [ ] 자동생성분 미커밋(feat/purpose-policy 워킹트리)

---

## 2026-07-11(3) — Claude CLI — feat/purpose-policy 통합 브랜치 (내 링크·purpose + yoonhs 재설명·이유라벨 머지) + 통합 라이브 검증

### 사용자 요청
- yoonhs 새 작업과 내 미커밋 작업을 합쳐 새 브랜치로 커밋·푸시 → 통합 결과 오류 검증.

### 한 일
- `feat/purpose-policy` 분기(구명 wizard-links-purpose에서 개명): 내 작업 3커밋(링크 `5b5e3e1`·purpose 정책 `0b74f5d`·docs `df30a24`) + `origin/feat/yoonhs-integration`(재설명 루프·이유 라벨·ingest 3→8) 머지 `ab292fc`, 원격 푸시.
- 충돌 2건 해소: `learning/service.py` import(양쪽 유지 — `purpose_directive_of` + `generate_supplement`/grading 확장), `WORK_LOG.md`(세션 양쪽 전부 보존).

### 결과 / 검증 (통합 코드 실 라이브, course 50307f29)
- **접점1 — 복습 수집**: 내 cap(exam=8) + 팀원 (개념,이유) 튜플 반환이 한 호출에서 동시 발화 — 8개 수집, 각각 이유 문장("복습 시점이 된 개념이에요…") 부착
- **접점2 — 챕터 생성**: exam으로 실생성 → 복습 섹션 개념 8·블록 15 **전부 meta.reviewReason 스탬프** + 본편 인출 전부 tracked=t
- **접점3 — 재설명 루프**: mcq 오답 제출 → `nextAction=supplement` → `POST /blocks/:id/supplement` 실 LLM 진단("위조를 …로 오해") + misconception=True + 맞춤 재설명 수신
- 머지 후 hobby 절 read-complete 200 재확인, tsc 0, 통합 import(main.app) OK
- 로그 ERROR 8건은 통합과 무관 — 사용자가 `.fbx`(3D 파일)를 주교재로 업로드 시도 → Upstage 파서 415 거부(정상 방어). 부수 관찰: 확장자 사전검사 없음(octet-stream 통과) + 배치 실패 시 보조 문서가 processing 잔존 — 개선 후보로 기록
- 상태 원복(purpose=career)

### 열린 이슈
- [ ] 업로드 확장자/매직바이트 사전검사(fbx 등 비PDF 차단) + 배치 실패 시 잔여 문서 상태 정리
- [ ] 재설명(_supplement_prompt)에 purpose 지시문 미적용 — 성향만 반영 중(후속 후보)

---

## 2026-07-11(2) — Claude CLI — 학습 목적(purpose) 엔진 정책화: PurposePolicy(문항 구성·tracked 게이트·복습 cap·SM-2 계수)

### 사용자 요청
- 목적별 학습 '방식' 차이(시험=암기·문제 다수, 취미=부담 없이 등) 브레인스토밍 → 설계 확정("그대로 진행").

### 추론 / 결정
- **목적 = 학습 엔진의 강도 프리셋** — 새 모듈 `learning/policy.py`의 `PurposePolicy`(retrieval_directive·tracked_retrieval·review_cap·sm2_interval_factor) 테이블 하나로 표현. 미설정/미지 값 = 현행 동작(하위호환).
- **게이트 로직은 분기하지 않음** — 취미의 게이트 완화는 인출 블록을 `tracked=False`로 '생성'해서 달성: 기존 `complete_section_by_reading`의 "tracked 0개면 열람 완료" 규칙이 코드 수정 없이 발동. 정책이 전부 데이터(생성물 속성+상수)라 상태머신 리스크 0.
- 코드 정찰 결과 반영: 오답 재큐는 기존 오답노트 우선 복습 수집이 이미 수행 → 시험은 cap(8)·주기(0.7)만 강화. 게이트는 이미 「풀면 진행」이라 강화 불필요. 난이도는 불변(§2.3 — 목적이 아니라 수준의 함수), STEP3 카피에서 "난이도" 문구 제거.
- SM-2 계수는 interval에만 적용(ease 불변 — 목적 변경이 학습 이력을 오염하지 않게), 하한 1일.

### 한 일 (정책 테이블: exam 8/0.7/tracked, career 5/1.0, culture 3/1.5, hobby 0/untracked)
- `learning/policy.py` 신규 — 정책 4종 + `policy_of()` · `generator.py` `GenerationInput.tracked_retrieval` + learn 블록 `tracked = 타입기본 AND 정책` + 밀도·유형 지시문은 스타일 지시문과 합류 · `review/sm2.py` `interval_factor` 파라미터 · `service.py` ①`_prepare_generation_input` 정책 소비 ②`run_chapter_generation` `_REVIEW_CAP=5` 고정 → 정책 cap(0이면 복습 수집 스킵) ③`record_attempt` SM-2 갱신에 계수 · 프론트 STEP3 카피 "난이도와 문제 유형"→"문제 유형과 학습 방식"

### 변경 파일
- backend: `features/learning/{policy(신규),generator,service}.py`, `features/review/sm2.py` / frontend: `pages/CreateCoursePage.tsx`(카피 1줄)

### 결과 / 검증 (실 mlv2 Docker+DB+LLM, course 50307f29)
- 순수: 정책 테이블 4종+미지값 폴백, exam 프롬프트에 스타일+밀도 지시문 동시 주입, SM-2 interval 20일 정답 시 기본 50 / 시험 35 / 교양 75일 + 오답 하한 1일 — PASS
- **hobby 라이브**: purpose=hobby로 챕터 생성 → 인출 블록(cloze3·mcq2·explainBack2) **전부 tracked=f** + 복습 섹션 0
- **exam 라이브**: purpose=exam으로 다른 챕터 생성 → 인출 **전부 tracked=t**, 절당 인출 4~7문항(밀도 지시 반영 경향)
- **게이트 실증(HTTP)**: hobby 절 read-complete → **200 completed**(문제 안 풀고 완료), exam 절 → **409**("채점 대상 블록이 있는 절은 열람만으로 완료할 수 없습니다") — tracked 정책만으로 게이트 차등 성립
- **SM-2 계수 실배선**: mastery interval 20일 세팅 후 exam 상태에서 review 정답 attempt → **interval 35일**(기본이면 50) 기록
- **복습 cap 실증**: due 개념 10개 시딩 → 수집이 exam 8·culture 3·hobby 0(스킵) 정확, exam 챕터 생성 시 「복습 · 오답 체크」 섹션이 **개념 정확히 8개**·블록 15개(전부 tracked)로 물리 생성. 백엔드 예외 0, tsc 0 에러. 테스트 코스 purpose는 career로 원복

### 열린 이슈
- [ ] 3단계 시험 트랙 미착수: D-day(enrollments 컬럼) → 모의고사(복습 섹션의 누적 확장) → 기출 연동(STEP2 kind 배선 선행)
- [ ] yoonhs 워킹트리 미커밋(링크·purpose v1 포함) — 커밋 여부 사용자 결정 대기

### 다음 액션
1. 브라우저에서 목적별 체감 확인(취미 코스 만들어 절 완료 UX 등) 후 커밋 결정
2. 시험 트랙(D-day부터) 착수 여부 결정

---

## 2026-07-11 — Claude CLI — 위저드 STEP2 링크 보조자료 참조 + STEP3 학습 목적(purpose) 배선 구현·E2E

### 사용자 요청
- STEP 2 보조자료(기출·링크·필기)가 "앞서 올린 PDF에 도움되는 링크 넣으면 거기서도 참조"하는지 테스트, 없으면 구현. STEP 3 학습 목적(시험·실무·교양·취미)도 확인, 없으면 구현.

### 추론 / 결정 (테스트 결과 = 현황)
- **보조 PDF 파일**: 이미 배선돼 있었음 — upload-batch(roles) → `extract_graph=False`(청크·임베딩만) → RAG `_course_doc_ids`가 supplementary 포함.
- **링크**: 완전 미구현 — 프론트가 수집만 하고 전송 안 함(`filter(m=>m.file)`이 링크 제외), 백엔드 URL 섭취 경로 없음 → **구현**.
- **purpose**: 유실 — 위저드가 `?purpose=`로 넘기지만 DiagnosisPage가 안 읽고, 온보딩 `_complete`도 `finalize_onboarding`에 안 넘겨 항상 기본 "exam". `enrollment.purpose` 소비처도 전무 → **배선+소비 구현**. 소비는 STEP3 카피("목표에 맞춰 조절") 대비 최소 정직선: 성향 지시문과 동일 패턴의 결정적 스타일 지시문(§2.2 가드 — 난이도·범위·분량 불변, `difficulty_hint=2` 유지).
- 링크 fetch는 stdlib HTMLParser(신규 의존 0), 실패는 코스 전체가 아닌 해당 링크만 failed(보조자료는 근거 하나 빠질 뿐). yoonhs 브랜치 워킹트리에서 작업(미커밋).

### 한 일
- **링크**: `documents/linkfetch.py` 신규(httpx fetch+HTML→평문, 헤딩은 마크다운 #으로 보존해 sectioning 절 경계 재활용, script/nav/footer 제거, <80자 본문 거부) · `service.py` `_ingest_link`(fetch→청킹→임베딩, 제목으로 filename 치환, storage_url=URL) + `run_batch_pipeline` url 분기(개별 실패 무시) + `create_batch_stub` url 메타 · `router.py` upload-batch `links` Form(http/https 검증) · 프론트 `uploadDocumentBatch(files,title,links)` + `CreateCoursePage` suppLinks 전송(링크 있으면 배치 경로)
- **purpose**: `StartRequest.purpose` + 온보딩 start가 화이트리스트(exam|career|culture|hobby) 검증 후 세션 state 보관 → `_complete`가 `finalize_onboarding(purpose=…)` 전달(기존 `enrollment.purpose or purpose` 로직 활용, 컬럼 기본값 NULL이라 정상) · `generator.py` `_PURPOSE_DIRECTIVES` 4종+`purpose_directive_of()` + `GenerationInput.purpose_directive` + build_prompt 주입(성향 지시문과 병렬) · `learning/service._prepare_generation_input`이 enrollment.purpose 소비 · 프론트 DiagnosisPage `useSearchParams`→`startOnboarding(courseId, purpose)`

### 변경 파일
- backend: `features/documents/{linkfetch(신규),service,router}.py`, `features/diagnostic/{schemas,router,onboarding}.py`, `features/learning/{generator,service}.py`
- frontend: `features/documents/api/uploadDocument.ts`, `features/diagnostic/api/onboardingApi.ts`, `pages/{CreateCoursePage,DiagnosisPage}.tsx`

### 결과 / 검증 (실 mlv2 Docker+DB+Solar LLM, course 50307f29)
- 순수 로직: purpose 4종+미지값 중립, build_prompt 성향+목적 동시 주입, html_to_text(스크립트·nav·footer 제거, 제목 추출) 전부 PASS. 프론트 tsc 0 에러.
- **링크 E2E**: 컴윤 10주차 PDF(primary)+위키 「정보 윤리」 링크 배치 업로드 → ready. 링크 문서: role=supplementary, filename=페이지 제목 치환, **청크 2·임베딩 2**. `search_concept_chunks`("상충되는 윤리적 책임") top-3 중 **위키 링크 청크 2개 포함** — "올린 PDF에 도움되는 링크를 거기서도 참조" 실증.
- **purpose E2E**: 온보딩 start(purpose=career)→12스텝 완주 → **enrollment.purpose='career'** 영속(diag_status=completed) → 실 `_prepare_generation_input`이 career 지시문 산출, 생성 프롬프트에 「[학습 목적: 실무·커리어]」 주입 확인.

### 열린 이슈
- [ ] 링크 v1 한계: JS 렌더링(SPA) 페이지는 본문 추출 빈약(<80자 거부로 방어), PDF 링크 미지원, 위키 청크에 언어목록·외부링크 등 보일러플레이트 일부 잔존(RAG 유사도가 걸러주지만 정제 여지)
- [ ] STEP2 kind(기출/필기 구분)는 여전히 UI 수집만 — 하류 소비처 생기면 배선
- [ ] yoonhs 브랜치 워킹트리 미커밋 — 커밋 여부 사용자 결정 대기

### 다음 액션
1. 사용자 브라우저 확인(위저드 STEP2 링크 추가→생성→학습 블록에 링크 근거 반영) 후 커밋 결정
2. 기존 우선순위 유지 — ISSUE-005 재설명 루프 / ISSUE-017
---

## 2026-07-11 — Claude CLI — 통합 반영·스택 전환 (기록 세션, 코드 변경 없음)

### 사용자 요청
- 오늘 작업(아래 두 세션) 마무리 후 상황 기록. AI 튜터 채팅 실동작은 **홀드**(팀 상황 대기).

### 상황 정리
- **통합 반영**: `feat/yoonhs-work`의 오늘 2커밋(재설명 루프 `78f81d9` + 이유 라벨 `593606e`)이 `feat/yoonhs-integration`에 **FF 머지·origin 푸시 완료**(사용자 수행). 통합본 = 오늘 작업 포함 최신.
- **스택 전환**: mlv2 스택을 `~/metalearn-work` 마운트 → **`~/metalearn-placement`(통합본) 마운트**로 전환. DB 볼륨 유지(코스·계정 보존), head 0020 정합, backend 58001·frontend 55173 정상(200). 통합본 코드에 supplement 라우트 포함 확인.
- **팀 동향(카톡, 2026-07-11)**: 소민섭 — 스텝2(URL 참조 ingest)는 JS 렌더링 사이트 한계 + 효용 논의 끝에 **보류**, 스텝3(학습 목적 purpose: 시험·자격증/실무·커리어/교양·흥미 → 프롬프팅으로 커리큘럼 유형 분기) 착수. purpose는 생성 시점 맞춤이라 우리(학습 루프) 작업과 층위 분리 — 우리 쪽 재설명 프롬프트는 `build_prompt` 밖에 분리해 충돌 예방해둠.

### 오늘 세션 합계 (아래 두 블록 상세)
1. **재설명 루프**(ISSUE-005 핵심): `POST /blocks/:id/supplement` — 오답 진단+맞춤 재설명, misconception 배선(dead branch 발화), AI튜터 패널 표시
2. **이유 라벨**(§4 변화 가시성): 복습 카드 `meta.reviewReason` + 선행 챕터 `ChapterNode.reason`(attempts 파생, 마이그레이션 0)

### 다음 액션
1. (홀드) AI 튜터 채팅 실동작 — 보충 진단·재설명이 컨텍스트 재료로 준비된 상태
2. ISSUE-017 external_refs / dev 머지(팀 합의) — 스텝2 보류로 external_refs 수집 방식 여전히 미정
3. 소민섭 purpose 머지 시 `_prepare_generation_input`/`build_prompt` 접합부 확인

---

## 2026-07-11 — Claude CLI — 이유 라벨 구현 (변화 가시성 §4: 복습 카드 + 선행 챕터)

### 사용자 요청
- 재설명 루프에 이어 다음 액션 1번(이유 라벨) 진행 — "커리큘럼은 말없이 변하지 않는다"(SERVICE_OVERVIEW §4)의 실체.

### 추론 / 결정
- **마이그레이션 0**: 복습 이유는 생성 시 `blocks.meta.reviewReason`(기존 JSONB) 스탬프, 선행 이유는 `attempts.meta.prereqChapterId`에서 **조회 시 파생 계산**(기획 원칙: 파생값은 계산으로) — 스키마 변경 없음(스쿼시 이슈와 무충돌).
- 이유 문장은 **서버가 완성해 내려준다**(프론트 파생 조립 금지 — 변화의 근거는 판정한 쪽이 말한다). 프론트 기존 파생 문구는 폴백으로 유지.
- 복습 이유 3종: 오답노트(연속 오답 횟수 반영) / strength 미달("아직 확실히 익히지 못한") / SM-2 due("N일 전 배운 개념, 잊힐 때가 됐어요" — 정본 §4 문구).

### 한 일
- backend: `learning/repository.py`(`get_wrong_note_concepts`·`collect_review_concepts`가 (개념, 이유) 반환 + `_sm2_due_reason`), `learning/service.py`(복습 생성 루프에서 meta 스탬프), `learning/schemas.py`(BlockMeta.review_reason)+`serializer.py`(통과), `curriculum/repository.py`(`prereq_triggers_by_chapter` — attempts.meta JSONB 파생), `curriculum/schemas.py`(ChapterNode.reason)+`router.py`(문장 조립)
- frontend: `getCourseTree.ts`(TreeChapter.reason), `blocks/types.ts`(meta.reviewReason), `registry.tsx`(복습 카드 배지+이유 배너), `LearningPage.tsx`(선행 배너 서버 reason 우선), `CurriculumPanel.tsx`(서브타이틀 서버 reason 우선), `mock.ts`(타입)

### 결과 / 검증 (실 mlv2 DB + 실제 Solar LLM)
- 복습 수집: 오답노트 "지난 학습에서 틀렸던 개념이에요…" / SM-2 "5일 전 배운 개념, 잊힐 때가 됐어요…" 정확 산출
- 실 LLM 복습 블록 2개 생성→스탬프→서빙 봉투 `meta.reviewReason` 와이어 확인
- 트리 API(HTTP): prereq 챕터 `reason="'데이터 통신의 개념과 역사' 문제를 틀렸을 때 이 개념이 기반이라고 판단해서, 먼저 다지도록 앞에 끼워 넣었어요"`, book 챕터는 null
- 프론트 tsc 무오류. 테스트 상태 전부 원복(스크립트 내 자동 원복 확인)

### 열린 이슈
- [ ] (관찰) 기존에 이미 생성돼 저장된 복습 블록에는 reviewReason이 없음(신규 생성분부터) — 재생성 시 자연 해소

### 다음 액션
1. ISSUE-005 잔여: AI 튜터 채팅 실동작(보충 진단·재설명을 컨텍스트로)
2. ISSUE-017 external_refs / dev 머지(팀 합의)

---

## 2026-07-11 — Claude CLI — 재설명 루프 구현 (ISSUE-005 핵심: 오답 진단 + 맞춤 보충 + misconception 배선)

### 사용자 요청
- 정본(SERVICE_OVERVIEW) 대비 학습 진행 과정의 부족한 부분 실사 → 개입 사다리 ②(보충)가 껍데기(`next_action=supplement` 라벨만, 재설명 생성 없음)임을 확인 → 재설명 루프 구현.

### 추론 / 결정
- **엔드포인트 분리**(`POST /blocks/:id/supplement`): 재설명 LLM 콜(수 초)을 채점 경로에 얹지 않는다 — reveal은 즉시, 재설명은 뒤따라 도착. 프론트가 `nextAction=supplement` 수신 시 자동 호출.
- **1콜 = 진단+재설명**: 학습자의 실제 오답(mcq는 보기 텍스트로 풀어서)·missed_points를 입력으로 "무엇을 오해했나"(diagnosis, misconception 여부)와 그 오해를 겨냥한 재설명을 함께 생성. 근거 수집은 첫 생성과 동일 경로(`_prepare_generation_input` 재활용 — 성향 지시문 포함), faithfulness 게이트 동일 적용(불통과 재생성 1회 → 근거 인용 폴백).
- **비영속**: blocks는 유저 무관 테이블이라 개인화 재설명을 넣으면 타 유저 유출 → 응답은 ephemeral, 진단만 해당 시도 `attempts.meta.supplement`에 병합 저장.
- **misconception 배선**: `record_attempt`가 직전 시도 meta의 misconception 플래그를 읽어 `localize()`에 전달 — dead branch였던 misconception cause가 발화 가능. 오개념이면 선행 삽입 억제(cause≠prerequisite → [4c] 스킵), 처방=재설명 지속. 새 시도가 쌓이면 플래그 자연 소멸(최근 1건만 조회).
- **프롬프트 별도 함수**(`_supplement_prompt`) — `build_prompt` 불변(소민섭 purpose 프롬프팅 작업과 충돌 회피).

### 한 일
- backend: `generator.py`(SupplementInput/Result·프롬프트·파서·폴백·`generate_supplement`·`question_context_from_block`), `repository.py`(`get_latest_attempt_for_block`·`attach_attempt_analysis`·`get_recent_misconception`), `service.py`(`generate_block_supplement` + record_attempt misconception 배선 + `_format_user_answer`), `schemas.py`(SupplementResponse), `router.py`(POST /blocks/:id/supplement), `localization.py`(misconception reason 문구를 실제 신호원으로 수정)
- frontend: `api/getSupplement.ts`, `LearningPage.tsx`(오답+supplement/misconception 시 자동 fetch, 절 이동 시 리셋), `AiTutorPanel.tsx`(분석 중 버블 → 진단 배지+재설명 버블 — mock이던 패널에 첫 실 LLM 콘텐츠)

### 결과 / 검증 (실 mlv2 DB + 실제 Solar LLM, head 0020)
- 단위: 파서 정상/실패/빈값, mcq·cloze 문항 컨텍스트 추출, 폴백 인용, 프롬프트에 오답·성향·missed_points 포함 — 전부 PASS (임시 스크립트, 검증 후 삭제)
- mcq E2E(WAN 문항, 오답 제출): supplement 응답 = 오답("전송 거리가 넓다→빠를 것") 정면 겨냥 진단 + 원문 접지 재설명, misconception=true, fallback=false
- explainBack E2E("빠르고 싸다" 오답): missed_points(구문/의미/타이밍)가 재설명에 반영 + dev 성향(비유 선호)대로 비유(고속버스/화물선) 사용 — 성향 지시문이 보충에도 흐름 확인
- misconception 배선 E2E: 진단이 attempts.meta에 영속 → 2번째 오답에서 `cause.type=misconception` 발화(기존 dead branch) + `prerequisite=null`(선행 삽입 억제) 확인
- 프론트 `tsc --noEmit` 무오류(컨테이너). 테스트로 더럽힌 상태 원복(attempts 3건 삭제, mastery 2건·section_progress 1건 복구)

### 열린 이슈
- [ ] ISSUE-005 잔여: AI 튜터 채팅 실동작(입력창 무배선) — 이제 보충 진단·재설명이 대화 컨텍스트 재료로 존재
- [ ] `decide_intervention_stage`(hint_ladder) 여전히 미호출 — 재설명 루프가 reframe을 대체했으므로 정리 or hint 단계로 흡수 검토
- [ ] 복습 카드·선행 삽입 "이유 라벨"(정본 §4 변화 가시성) — 백엔드 reason 미노출

### 다음 액션
1. 이유 라벨(복습 카드·선행 삽입에 reason 텍스트) — 작은 작업, 데모 효용 큼
2. AI 튜터 채팅 실동작(보충 컨텍스트 물고 들어가는 LLM 채팅)

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
