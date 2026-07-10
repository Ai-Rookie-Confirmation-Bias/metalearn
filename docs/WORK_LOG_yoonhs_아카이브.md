> 📦 **아카이브(읽기 전용)** — `feat/backend-ai-core` 계열 세션 1~16(2026-07-05~08: 학습엔진·병합 트라이얼·성능·조립) 기록. 현행 공용 일지는 [`WORK_LOG.md`](./WORK_LOG.md).

# MetaLearn — WORK_LOG (작업 일지)

> **담당 브랜치**: `feat/backend-ai-core` (yoonhs). 이 파일은 **매 세션의 대화·결정·작업을 시간순으로 쌓는 일지**다.
> 팀원/다른 LLM이 이걸 읽으면 "이 브랜치가 무엇을, 왜, 어떻게 해왔는지" 바로 이해할 수 있어야 한다.
> 제품·아키텍처·원칙 같은 잘 안 바뀌는 것은 `CLAUDE_CONTEXT.md`에 있다 — 여기 중복 쓰지 말 것.

## 기록 규칙
- 세션마다 **구분선 아래 맨 위에 새 블록을 append**(최신이 위).
- **세션 블록 템플릿**:
  ```
  ## 날짜 — 에이전트 — 한 줄 요약
  ### 사용자 요청
  ### 추론·결정 (왜 이렇게 했나)
  ### 한 일
  ### 변경 파일
  ### 결과
  ### 검증 (실행한 명령·결과)
  ### 다음 액션
  ```
- 상단 **'열린 이슈' 표를 유지**. **실제로 실행·확인한 검증 없이는 절대 `closed`로 바꾸지 않는다.**
- **에이전트 시작 시**: `CLAUDE_CONTEXT.md` + 이 파일(최신 블록 + 열린 이슈 + 다음 액션)을 먼저 읽고 시작.
- **에이전트 종료 시**: 새 블록 기록 + 이슈 상태 갱신. 사용자가 "기록해줘"라고 하거나, **에이전트가 마무리 시점에 "기록할까?"를 먼저 제안**한다.

---

## 열린 이슈
| ISSUE | 우선순위 | 상태 | 내용 |
|---|---|---|---|
| ISSUE-001 | 높음 | open | **마이그레이션 계보 분기 + PK 타입 분기** — backend-ai-core(…`0012_blueprint_schema`) vs parsing(…`0013_seed_contract`)이 `0002`부터 상이. **PK 정답 확정(2026-07-06 세션2): dev/docs/SCHEMA.md=정본 → UUID.** 내 브랜치=정합, parsing=Integer(이관 필요). parsing 정합 목록: PK Integer→UUID / `enrollments.*_concept_id`→`*_concept`+`diag_status`·`diag_q_count` / `concepts.key` NOT NULL+UNIQUE / `concepts.source` `'document'`→`book\|ai_prereq`. **제안 방향**: 정합 후 `versions/*` 삭제→정본(UUID) 모델로 단일 `0001_initial` 스쿼시(prod 데이터 없어 무손실). ⚠️단독 금지 — parsing 팀원과 동시 실행. **트라이얼 실증 완료(세션12)**: 로컬 전용 `trial/parsing-merge`(worktree `~/metalearn-mergecheck`, 커밋 `a3d573e`)에서 UUID 정본 병합 전 과정 실증 — 빈 DB 0001→0015 적용·서빙 무회귀·진단/씨앗 실호출 PASS. 남은 것 = 팀원 리뷰 + 스쿼시 동시 진행 |
| ISSUE-002 | 높음 | 해결(서버측) | **선행 삽입 실행부 완료(세션5)** — `cause=prerequisite`(국소화 blame) 구동으로 `chapters(origin='prereq')` 동적 삽입(현재 앞 order-5, pending)·멱등·응답 표면화. 검증됨. **커서(복귀 자동화)도 완료(세션6, learning_cursor)** — push/pop/resume 검증. **남은 것**: 프론트 라우팅 연동만 |
| ISSUE-003 | 중간 | 구현·검증 | **faithfulness 게이트 구현(세션9)** — 블록 단위 Solar 근거 대조(`generator.check_faithfulness`, §2.5A [3]). 명시적 불통과만 폐기, 판정실패/파싱불가는 관대 폴백(net-additive). analogy 면제. 검증: 근거일치 통과 / 지어낸 주장(1850년 파리 발명) 폐기. **남은 것**: 위험도 차등(정의·수치 고위험 강검증), 문장 단위는 §4에서 금지 |
| ISSUE-004 | 중간 | 구현·검증 | **RAG 임베딩 검색 구현(세션9)** — `search_concept_chunks`: 개념 query 임베딩 vs 청크 passage 임베딩 pgvector cosine top-K, 없으면 키워드 폴백. 검증: 키워드 없는 의미 질의로 트랜잭션 청크 TOP1. **남은 것**: 병합 후 `concepts.embedding`(parsing) 소비 전환 |
| ISSUE-015 | 높음 | open | **RAG 임베딩 모델 계약(parsing 합의 필요)** — 정확도 위해 **비대칭**: 개념=`embedding-query`(parsing 이미 함), 청크=`embedding-passage`(parsing 현재 query모델 → passage로 변경 1줄). 둘 다 4096. 우리 downstream은 `concepts.embedding` 소비(재임베딩 회피). 병합 시 확정 |
| ISSUE-005 | 중간 | open | **auth 임시** — `core/deps.py` `X-User-Id` 헤더. JWT 아님. User 모델도 email/password 구형(소셜 provider/uid 아님) |
| ISSUE-006 | 중간 | open | **variant 잠정** — 부분집합 필터로만 구현. `blocks.variant` 컬럼 신설 여부 팀 미결 |
| ISSUE-007 | 낮음 | open | `dev_seed_serving.py` 임시 픽스처 — 씨앗 완성 시 제거 |
| ISSUE-008 | 중간 | 구현·검증(데모) | **로컬 EXAONE 런타임 — 스텁 → 실구동(세션18, 브랜치 `feat/ondevice-exaone-mvp`)**. EXAONE-4.0-1.2B-Q4 를 llama.cpp CPU로 서빙, 오프라인 채점·힌트·꼬리질문·꼬리채점 E2E 검증(HCI PDF). 온라인 생성=K-EXAONE-236B(Friendli). **남은 것**: 4-bit 브라우저 실행(결선), 채점 정확도(ISSUE-020 벤치→유사모델 베이스라인→LoRA H100 480h), 온디바이스 캐싱(ISSUE-022). 근거: `docs/07_09 온디바이스-EXAONE 경계 결정문.md` + ondevice/README |
| ISSUE-009 | 미정 | open | 평가/맞춤 설계 미결: 성향평가 문항·저장 스키마, 오답노트 저장 구조, `concept_chunks` 매핑 테이블, 41-type 공유 스키마 |
| ISSUE-010 | 중간 | 진행중 | **원인 국소화 1차 완료(세션3)** — BKT×DAG로 hold/prerequisite(blame)/content 판정·검증(`bkt.py`/`localization.py`). **남은 것**: Router×cause 연결, 선행별 BKT 재추정, 오개념 신호(explainBack), 콜드스타트 사다리(프로브/클러스터 warm start), depth=DAG 최장경로 실계산 |
| ISSUE-014 | 높음 | 우리측 완료 | **프론트 봉투 계약 불일치(feat/front-learning ↔ 우리 serializer)** — **우리측 4개 정합 완료·검증(세션8)**: 봉투 kind·Section id/title·cloze→segments·채점 reveal(정답+해설). **남은 것(프론트측)**: McqBlock/ClozeBlock을 라운드트립 채점으로(클라 answerIndex 제거), reveal로 정답/해설 표시. — 아키텍처는 정합(같은 5 type·봉투·registry). data 모양 어긋남: **mcq `answerIndex`**(프론트 클라채점 vs 우리 스트립 → 프론트 라운드트립 재설계 필요) · **cloze**(프론트 `segments[]` vs 우리 `text`+`blanksCount`) · 봉투 `kind` 없음 · SectionPayload `{id,title}` vs `{sectionId,variant}` · mcq `explanation` 스트립. **우리측(저비용)**: kind 추가·section id/title·cloze→segments 변환·채점응답에 정답+explanation. **프론트측**: mcq/cloze 라운드트립 채점. ※ 프론트 팀원 ~3주 부재 → 우리가 마무리 가능성 |
| ISSUE-013 | 중간 | open | **경계 확정: 진단평가=parsing, "진단 후→커리큘럼 생성"부터가 우리(2026-07-06)** — 수준 **판정**은 진단 산출물이므로 `initialize_placement`는 *판정 계산*이 아니라 **판정 수령·기록·킥오프**여야. 현재는 floor/ceiling을 커리큘럼 순서로 근사 계산 중 → 병합 시 parsing 진단 mastery 판정을 그대로 수령 + 진단 안 한 개념만 위치로 채우는 쪽으로 좁힌다. (localization은 수업 중 인출 기반이라 진단 아님 — 우리 영역 유지) |
| ISSUE-012 | 높음 | 해결(소비자측) | **지식그래프 방향 규약** — parsing 규약 채택 확정(2026-07-06, `docs/GRAPH_ORIENTATION_CONTRACT.md`): 엣지 `from=의존→to=선수` / `depth 클수록 선수(스파인=0)` / 진행축=커리큘럼 순서. 내 placement·localization 정합 완료·검증. **남은 확인**: 병합 시 parsing이 실제로 이 규약대로 생산하는지(특히 depth=DAG 최장경로) 대조 |
| ISSUE-011 | 중간 | 구현(integration) | **다중자료 코스 — `feat/yoonhs-integration`에 1:N 구현(세션16, 커밋 936b702).** `Document.course_id/seq/role` 추가(마이그 0018, Course.document_id는 앵커로 하위호환), `/upload-batch`(primary 순서·supplementary RAG), build_tree/placement/RAG 다중문서화. 4-PDF E2E 검증. ⚠️ dev/SCHEMA.md 정본은 `course_documents` N:N — 이번 구현은 Document 역참조 방식이라 **정본 스키마와 다름**(병합 시 조율). Document 스키마 변경은 parsing 영역 → 협의 필요 |
| ISSUE-019 | 🔴높음 | open | **이벤트 루프 데드락(실사용 발견 2026-07-07)** — 진단 문항 생성이 **DB 트랜잭션을 연 채(enrollments 락 보유) LLM 콜을 await** + 다른 요청의 동기 UPDATE가 그 락을 이벤트 루프 스레드에서 대기 → 서버 전체 무응답(CPU 0%). `pg_terminate_backend`로 복구. 수정: ①LLM 콜 전 커밋/트랜잭션 분리(특히 diagnostic·documents ingest) ②async def 안의 동기 SQLAlchemy를 threadpool로(또는 엔드포인트 sync화). 동시 사용(업로드+진단) 시 재현 — parsing·우리 공통 해당 |
| ISSUE-018 | 낮음 | open | **성능 후속(세션11에서 미룬 것)** — ① 다음 챕터 프리페치: 커서 advance 시 다음 챕터 `pending`이면 백그라운드 생성 트리거(`claim_generation` 멱등이라 안전) → 체감 대기 0. ② explainBack 채점 콜 타임아웃 분리: 유저가 기다리는 동기 경로인데 생성과 동일 설정(120s·재시도 최대 5회) 공유 → 채점만 ~15s·재시도 1회로(실패해도 키워드 폴백 있음). ※ 주의: parsing 브랜치가 ISSUE-016~017을 자체 번호로 사용 중 — 번호 충돌 있음, 통합 시 이슈 번호 체계 합치 필요 |
| ISSUE-020 | 🔴높음 | open | **채점 골든 라벨 벤치(멘토링 2026-07-09, 최우선 전제)** — 온라인(Solar)·오프라인(EXAONE) 채점 공통. 실측: 대형 Solar도 빈칸 채점 비일관(FN 취지맞는데 오답 / FP 근접오답을 정답). 필요: 문항×인간판정 라벨셋 + 정확도·오채점률(FN·FP 분리) 스크립트. 측정 없이는 파인튜닝 필요여부·H100 투입 판단 불가. 근거: `docs/07_09 온디바이스-EXAONE 경계 결정문.md` §3·§5 |
| ISSUE-021 | 중간 | open | **EXAONE 서비스화 라이선스 문의(멘토링 2026-07-09)** — 대회·데모는 문제없음 확인. 서비스/창업 단계는 주최측 협의 필요 → 문의 채널 확인 후 진행 |
| ISSUE-022 | 중간 | open | **온디바이스 경계·캐싱(멘토링 2026-07-09 확정)** — 경계: 미리계산가능=온라인(생성+근거검증) / 실시간=오프라인(채점·힌트·재질문). 필요: ①콘텐츠 생성 스키마를 오프라인 파생 가능하게 확장(힌트 재료·예상 오답·재질문 seed) ②"검증된 콘텐츠" 온디바이스 캐싱 계층 ③로딩·첫토큰 지연 UX 은폐(처리중 표시+프리페치). 근거: `docs/07_09 온디바이스-EXAONE 경계 결정문.md` §1·§4·§6 |

---

## 세션 기록 (최신이 위)

---

## 2026-07-10 (세션19) — Claude (Opus 4.8) — 진짜 통합본 병합 검증 + 작업 브랜치 분기 + ingest 속도 1차(실측 2배)

### 사용자 요청
소민섭 성향 진단(`redesign/diagnostic-profiling`) + OAuth를 통합본 `feat/yoonhs-integration`에 병합해 "진짜 통합본" 완성 → 거기서 개인 작업 브랜치 분기 → 강사 피드백(파싱 5분) 대응 ingest 속도부터 착수·실측.

### 추론·결정 (왜)
- **redesign 병합 = FF**: 우리 통합본(57796e7)에서 분기한 3커밋이라 충돌 0(성향 진단 재설계·학습확인루프·docs). E2E 검증 전이.
- **OAuth 병합**(다른 세션 실행): 별개 라인 1커밋 + 마이그 `0017_oauth`가 0016을 가리켜 0018과 이중 head → **0020으로 재연결**해 해소.
- **작업 브랜치 격리**: 공유 통합본 오염 방지 위해 별도 워크트리(`~/metalearn-work`) + upstream 끊음(실수 push 방지). 공유 문서(SERVICE_OVERVIEW·DEV_GUIDE)는 참조, 세션 로그는 이 파일에.
- **ingest 속도**: 개념추출(`_extract_all`)이 지배 비용인데 동시성 3이라 Solar 전역 8슬롯 중 5 유휴 → 8로. **문서 병렬화는 8 포화 후 같은 슬롯 경쟁이라 이득 작음(+공유 DB 세션 리스크) → 보류.**

### 한 일
- 통합 병합 검증(FF·마이그 단일 head), 작업 브랜치 `feat/yoonhs-work` 분기.
- `eee8681` 개념추출 동시성 3→8 (`config.EXTRACTION_MAX_CONCURRENCY`).

### 변경 파일
- `backend/app/core/config.py` (EXTRACTION_MAX_CONCURRENCY 3→8)

### 결과
- **진짜 통합본** = 성향 진단(소민섭) + OAuth + 다중PDF + 온디바이스 데모 전부 포함, 마이그 `0016→0018→0019→0020` 단일 head.
- ingest 추출 단계 **2배** 단축.

### 검증 (실행·결과)
- 독립 벤치(실 Solar `solar-pro3`, 20청크 추출): **동시성 3 = 10.0s / 8 = 5.0s = 2배, 429 0건** → 3→8 효과 확정, Solar 8동시 안전(레이트리밋 없음). Solar 8슬롯 포화가 백엔드 ingest 속도의 한계 = 이후엔 체감(스트리밍) 영역.
- 마이그 체인 grep으로 단일 head(0020) 확인.

### 다음 액션
- **A-2 채점 견고성**(SERVICE_OVERVIEW 백로그 1순위 — userInput 422·오채점 전파 차단) 또는 C 스트리밍(체감 속도, 강사 #4).
- 팀 조율: 마이그 스쿼시 0001~0020(소민섭 동시), 게이트 철학 합의(풀면진행 vs 2연속통과), OAuth 자격증명.

---

## 2026-07-09 (세션18) — Claude (Opus 4.8) — 온디바이스 EXAONE 데모 MVP 구현 + 특강 산출물 문서

### 사용자 요청
LG 특강 시간을 빌려 확증편향 팀 기획서(MetaLearn On-Device)를 **실제로 구현**. 목업 말고 실서비스 흐름(PDF 업로드→파싱→K-EXAONE 생성→1.2B 채점·꼬리질문·꼬리채점)으로. 이후 향후개선계획서 양식 채우기 + 기획서 갱신 + 푸쉬 + 기록.

### 추론·결정
- 새 워크트리·브랜치 `feat/ondevice-exaone-mvp`(worktree `~/metalearn-ondevice`, base backend-ai-core)에서 신규 제작 — 기존 브랜치 무오염.
- **모델 분할 확정**(멘토링·사용자 지시): 온라인 = `LGAI-EXAONE/K-EXAONE-236B-A23B`(Friendli, 서버리스 목록서 확인) 생성 / 오프라인 = `EXAONE-4.0-1.2B-Q4_K_M`(공식 GGUF) llama.cpp CPU로 채점·꼬리질문. 결정문 경계 그대로.
- Docker 아님 — 온디바이스답게 경량(llama-server :8080 + stdlib+pypdf 서버 :8000). 이 PC는 GPU 없음(Intel Iris Xe)·16코어 CPU.

### 한 일
- **온라인 파이프라인**: `pipeline.py` PDF(pypdf)→최대 5섹션→K-EXAONE 개념+검증 인출문제. `llm.py` K-EXAONE/로컬 공통 래퍼(+429 백오프, reasoning content-only, no_think).
- **오프라인**: llama.cpp 프리빌드(b9935)로 EXAONE-4.0-1.2B 서빙, `server.py`가 채점·힌트·꼬리질문·꼬리질문 채점을 로컬 :8080으로만 호출(오프라인 검증됨). 프롬프트는 작은모델 대응(예시-누수 제거, reason-first, non-answer 거부, bool 문자열 안전변환).
- **UI** `web/index.html`: 업로드→🌐온라인 생성→✈️오프라인 학습(빈칸 채점→꼬리질문→꼬리채점).
- **문서**: `team_확증편향_향후개선계획서_완성.docx`(양식 채움) + `team_확증편향_기획서_v2.docx`(실구현 2-모델 반영) — Downloads/.
- 커밋 `1245871` 푸쉬 → `origin/feat/ondevice-exaone-mvp`(소스만, 모델·바이너리 gitignore).

### 결과·검증
- **HCI PDF E2E**: 업로드→생성 68초·5개념 10문항 / 채점 ~2초(정답 인식, "사용 가능성"=Usability 의미매칭) / 꼬리질문·꼬리채점(non-answer 거부) 동작. 두 서버 라이브(:8000/:8080).
- 한계: 1.2B 채점이 지식오류 케이스서 오채점 있음(멘토링이 지목) → ISSUE-020 로드맵.

### 다음 액션
- 채점 골든라벨 벤치(ISSUE-020) — 데모 오채점률 수치화 → LoRA.
- 온디바이스 캐싱(검증 콘텐츠 저장)·꼬리질문 오답노트(ISSUE-022).
- 결선용 4bit 브라우저 실행·로딩 UX 은폐.

---

## 2026-07-09 (세션17) — Claude (Opus 4.8) — 멘토링 반영: 온디바이스·EXAONE 경계 결정문

### 사용자 요청
- (직전 세션) `07_09 진단+성향 파이프라인` 결정문 작성 → 이걸 들고 멘토링 Q&A 다녀옴.
- 멘토링 4문(오프라인 경계·라이선스·채점·실행환경) + 예비(신뢰성 지표) 답변을 전달 → 프로젝트에 반영·기록.

### 추론·결정 (왜 이렇게 했나)
- 멘토링은 제안서 핵심 차별화인 **오프라인/EXAONE 온디바이스** 축의 결정 → 진단+성향 결정문과 짝이 되는 **별도 결정문**으로 남김(서로 링크).
- **경계 규칙 확정**: *미리 계산 가능 = 온라인(생성+근거검증) / 사용자 입력 의존 실시간 = 오프라인(EXAONE 채점·힌트·재질문)*.
- 파생 조정: 씨앗/콘텐츠 생성을 **오프라인 파생 가능하도록 상세화**(힌트 재료·예상 오답·재질문 seed) 해야 오프라인 경로가 성립.
- **채점 신뢰성이 두 결정문 공통 우선순위 #1** — 다음 코드 착수점은 **골든 라벨 벤치**로 수렴(측정 없이는 파인튜닝/H100 투입 판단 불가).

### 한 일
- 결정문 신규: `docs/07_09 온디바이스-EXAONE 경계 결정문.md` (멘토 답변 표 + 경계 확정 + 심사 방어 + 채점/실행환경/지표/로드맵/발표서사).
- 열린 이슈 갱신: ISSUE-008 승격 계획 반영, ISSUE-020(채점 골든 라벨 벤치)·021(EXAONE 서비스화 라이선스 문의)·022(온디바이스 경계·캐싱) 신설.

### 변경 파일
- (신규) `docs/07_09 온디바이스-EXAONE 경계 결정문.md`
- `docs/WORK_LOG.md` (본 블록 + 이슈 표)
- ※ 직전 세션 산출물 `docs/07_09 진단+성향 파이프라인.md`는 이미 존재(커밋 전 untracked).

### 결과
- 멘토링 결정이 휘발되지 않게 문서로 고정. 다음 스프린트의 첫 착수점(골든 라벨 벤치)과 협의 필요 항목(라이선스 문의)이 명확해짐.

### 검증 (실행한 명령·결과)
- 코드 변경 없음(문서·일지만) → 실행 검증 대상 없음. 결정문 링크([[07_09 진단+성향 파이프라인]])·이슈 번호 정합만 확인.

### 다음 액션
1. **채점 골든 라벨 벤치** 착수(`feat/yoonhs-integration`) — 문항×인간판정 라벨셋 + 정확도/오채점률(FN·FP 분리) 스크립트. (ISSUE-020, 전제)
2. 유사 경량모델(K-EXAONE류) 채점 베이스라인 → 미달 시 LoRA(H100 480h). (ISSUE-008)
3. 콘텐츠 생성 스키마 확장(오프라인 파생 재료) + 온디바이스 캐싱 계층. (ISSUE-022)
4. 주최측에 서비스화 라이선스 문의. (ISSUE-021)

---

## 2026-07-08 (세션16) — Claude (Opus 4.8) — 배치고사 UI 전환·다중PDF 통합·방향 재점검 (브랜치 feat/yoonhs-integration)

> ⚠️ 이 세션 작업은 **`feat/yoonhs-integration`**(v2 `trial/full-assembly-v2` 기반 별도 통합 브랜치)에서 진행. 상세 로그는 그 브랜치의 `WORK_LOG.md`에도 있음. 여기엔 중앙 요약 + 열린 이슈 갱신만.

### 사용자 요청
v2 실구동 확인 → 진단 UI를 v2 배치고사로 전환 → 학습 설명 보강 → 다중 PDF 통합 → 코스 이름 입력 → 선행학습 명시화 → 진단 결과가 어디에 근거로 들어가는지 + 회의 방향 정합성 점검.

### 추론·결정 (중요)
- **구현이 회의 방향과 엇갈림을 발견 → 방향 재회의 필요.**
  - 회의(CLAUDE_CONTEXT 교육방향): 성향 진단 + 풀컨텍스트+성향맞춤 + 인출을 **"복습 시점"에 오답노트로** 반영, 반복진단 지양.
  - 구현: **수준(floor/ceiling)** 배치고사 + mastered/locked로 커리큘럼 축소 + **실시간 BKT**. 성향 진단·성향 스타일 맞춤·오답노트 weaving **없음**.
- 다중 PDF는 정본 방향(ISSUE-011)인 **1:N**으로 구현.

### 한 일 (feat/yoonhs-integration, 커밋 6개)
- 진단 UI → v2 배치고사(`/diagnostic/placement/*`) 전환(문항별 피드백 없이 즉시 다음).
- 개념 설명 보강: 프롬프트 "티칭 먼저→인출 나중" + faithfulness 완화(모순·날조만 차단).
- **다중 PDF 1:N 통합**: `Document.course_id/seq/role`(마이그 0018), `/upload-batch`, build_tree/placement/RAG 다중문서화, 슬러그 충돌 방지.
- 코스 이름 직접 입력 / 챕터 재생성 FK 크래시 픽스 / 선행학습 명시화(배지·"↳본편 준비"·진입 배너).

### 결과·검증
- 4-PDF 배치 E2E: 380개념·25챕터, 트리가 문서순(ch01→04) stacking, 배치고사·학습 정상. 프론트 tsc 0. 단일 PDF 하위호환 유지.
- 방향 정리 문서 `METALEARN_방향정렬.md`(노션 공유용, 현황+대조표+회의 안건).

### 다음 액션
- **방향 재회의** — 논점: ①성향 진단 넣나 ②수준 반영 타이밍(실시간 vs 복습) ③커리큘럼 축소(mastered/locked) 유지 ④진단↔커리큘럼 분리. → §논점2가 핵심(3·4는 따라옴).
- 회의 후 결정대로 코드 조정.
- (별개) 위키 429 refs 개선 · 문서 병렬 ingest · LearningPage courses[0] 라우팅 · 진단미완료 코스 트리 400.

---

## 2026-07-07 (세션15) — Claude (Fable5→Opus4.8) — 인계 전 전체 검증 + 두 브랜치 원격 푸시
### 사용자 요청
실사용 버그 수정(read-complete) 후 브랜치 전체를 검증해 "더 완벽한 인계본"으로 만들고, parsing 팀원이 확인 가능하게 `trial/parsing-merge`·`trial/full-assembly` 둘 다 push.
### 한 일 / 검증
- 회귀 스위트(검증 전용 DB `metalearn_verify`, 라이브 DB 무손상): **11/11 PASS** — alembic 0001→0015 / 시드→placement→챕터생성 8.1s→ready / 정답스트립 NO_LEAK / **치팅 방어**(correct=true 위조해도 4지선다 중 1개만 서버 정답판정) / 진단 스코핑(191→6문항)+진행률 신필드 / 복습 due·schedule / read-complete 409(채점절 거부) / 프론트 tsc / import+configure_mappers / 충돌마커 0.
- 코드리뷰: **ISSUE-019 데드락 근본원인 코드로 확정** — `diagnostic/service.py start()`가 트랜잭션(행 락) 연 채 `_ensure_questions`에서 LLM 다중 await, commit은 맨 끝. 우리 `record_attempt`는 LLM 채점을 행 락 **밖**에서 수행해 회피됨(대조 확인).
- 인계 문서 `HANDOFF_ASSEMBLY.md`(루트, docs/는 gitignore라 루트에) 작성 — 병합 결정·모델유니온·ISSUE-019·검증결과·협의 8항목·실행법.
### 결과 (원격 반영)
- `origin/trial/parsing-merge` = `a3d573e` (백엔드 전용: 성능튜닝+UUID포팅)
- `origin/trial/full-assembly` = `056b84f` (위 + 프론트 배선·진단 스코핑·버그수정 4종 + 인계문서)
- ⚠️ 중간사고: 워크트리가 full-assembly→parsing-merge로 전환된 채 인계커밋 생성 → parsing-merge에 잘못 안착. cherry-pick으로 full-assembly에 재배치 + parsing-merge를 a3d573e로 `--force-with-lease`(방금 푸시라 무손실). 최종 정합 확인.
### 다음 액션
parsing 팀원 리뷰 대기 — ISSUE-019 협의(1순위), 스쿼시 동시 진행, HANDOFF 8개 협의항목. 성향(MBTI) STEP A·선행 외부근거 수집 배선은 후속.

---

## 2026-07-07 (세션14) — Claude (Fable 5) — 진단 스코핑: 회의 결정(가벼운 계단식 체크) 구현 (커밋 305e38d)
### 사용자 요청
수학 코스(개념 191)에서 진단이 전 메인 개념 출제라 테스트 불가 + "화면을 회의 결정대로" 지적(성향+가벼운 체크, 문항 최소화). 진단 대상 = 커리큘럼 앞부분 + 선행 기반지식으로 명확화. 외부 선수지식은 학습 중 LLM 선행 삽입으로 충분하다고 합의.
### 추론·결정
- parsing의 게이티드 BKT는 유지하고 **스코핑만 추가**(개념당 1문항·계단 하강 구조가 회의안과 이미 부합). config 노브 3개: `DIAG_MAX_MAIN_CONCEPTS=6`(앞부분 메인 4 + 선수 프록시 2, depth 큰=기초 순) / `DIAG_MAX_TOTAL_QUESTIONS=10` 하드캡. 문서 뒷부분 미출제(시작점 판정에 불필요). 캡 밖 개념은 전파/사전값(억지 확정 없음) — 초기 해상도 낮음은 학습 중 확인 루프가 정밀화하는 의도적 교환.
- ⚠️ 진단은 parsing 담당 영역 — 코드 주석에 "회의 결정(2026-07-05) 구현 제안, parsing 리뷰 대상" 명시.
- 병행 교훈: 배선 때 parsing 풀-진단을 화면으로 그대로 감쌌다가 사용자 지적 — **기존 구현이 회의 결정과 어긋나면 신규 제작 전에 플래그할 것**.
### 검증 (수학 코스 실측)
start 15~26s·문항 6개(이차함수의 그래프 등 최선두 4 + 선수 2) / 전부 오답 시나리오 → 정확히 10문항 done / 혼합·전부 정답 완주 / seed build·placement 200(floor=이차함수의 그래프) / dev 코스(메인 4)는 전원 출제 그대로.
### 다음 액션
성향(MBTI식) STEP A 문항 설계+배선 / progress.total이 191로 표시되는 UI 눈금 조정 / 수식 문서 품질(LaTeX 정규화 검수·개념 과분할)은 parsing 피드백 목록 / 사용자: 쉬운 PDF로 재테스트 예정

---

## 2026-07-07 (세션13) — Claude (Fable 5) — full-assembly: 첫 수직 완주 (업로드→진단→씨앗→학습 화면)
### 사용자 요청
실 PDF 완주를 Swagger로 직접 실행(성공, "수학" 코스 생성) 후 → 트라이얼 백엔드 + integration 프론트를 병합해 배선까지, 화면으로 확인 가능하게. 본인이 직접 웹서버 띄워 UI/UX 육안 확인 예정.
### 추론·결정
- 로컬 전용 `trial/full-assembly`(= trial/parsing-merge + feat/integration-test). 충돌 16개, 원칙: **backend=trial(ours) / frontend=integration(theirs)** — 병합 후 backend diff 0줄이라 무회귀 구조 보장.
- 업로드 완료 시 책장 경유 없이 `/diagnosis/:courseId` 직행(진단 전 코스는 진행률 없음). 진단 화면은 AnswerResult(next_question·progress·done)만으로 구동, 해설 확인 후 수동 "다음"(학습 UX 일관).
- 책장 CTA는 "섹션 0개=진단 전" 프록시 판정 — 서버 diag_status 노출 필요(후속).
### 한 일
커밋 `242cd34`(병합) · `a87faad`(frontend 오버라이드 55173/58001/CORS) · `84a7b09`(배선): ①CreateCoursePage 실업로드(첫 파일, 로딩·에러 UI, 다중파일은 ISSUE-011 TODO) ②DiagnosisPage 신규(mcq 버튼/cloze·inverse 인출 입력, 오답 시 하위 문항 추가) ③done→seed build→placement→/library.
### 검증
pnpm build(tsc) PASS / UI API 시퀀스 실호출: diag start 201→answer 200×2→seed build 200(멱등)→placement 200(skipped=4 멱등)→generate→ready→봉투 200 / frontend 55173 200 + CORS preflight PASS / 재검증(본 세션) 전부 PASS.
### 다음 액션
- 사용자 육안 UI/UX 확인 → 피드백 반영
- 알려진 구멍: 대형 코스(수학 191개념) 진단 start 문항 배치 생성 느림·고비용(스코핑 필요) / 진단 세션 재진입 이어받기 없음 / diag_status 서버 노출 / ISSUE-011 다중자료
- 이 브랜치 3종(trial/parsing-merge·full-assembly) 처분은 parsing 팀원 리뷰 후 결정

---

## 2026-07-07 (세션12) — Claude (Fable 5) — parsing 병합 트라이얼: UUID 통합 실증 (ISSUE-001/015)
### 사용자 요청
parsing 병합이 1순위 → 팀원 대기 없이 우리가 먼저 병합을 실증. 팀원 브랜치는 절대 건드리지 말 것. 포팅·검증까지 완주 + 문서화.
### 추론·결정 (왜 이렇게 했나)
- **격리 원칙**: `feat/parsing`은 읽기 전용(`git show`만). 작업은 로컬 전용 브랜치 `trial/parsing-merge`(worktree `~/metalearn-mergecheck`), **push 안 함**. 목적 = MERGE_AGREEMENT_REQUEST의 "실행 가능한 증거물"(합의안대로 합치면 이렇게 된다) + 지뢰 지도 + 학습엔진 무회귀 보증.
- **정본 원칙**: 학습엔진·UUID 모델·프론트 = 우리, parsing의 상류 파이프라인(documents 정제·섹셔닝·개념추출·diagnostic BKT·seed 조립)은 로직 무변경으로 수용, 공용 파일은 합집합.
- **1단계(기계적)**: 15개 충돌 해소. solar.py는 양쪽 장점 통합(우리 튜닝 공유풀·세마포어 + parsing의 견고한 재시도[Retry-After 존중] + embed_batch/parse_document/generate_json). config 합집합(SOLAR_MODEL/SOLAR_CHAT_MODEL 공존). parsing의 Integer 모델을 임포트하는 documents/diagnostic/seed-service는 **보류 격리**(같은 테이블 이중 정의 → 서버 부팅 불가 실확인).
- **2단계(UUID 포팅, 서브에이전트 위임)**: 필드 유니온은 우리 모델에 흡수(아래). `documents/models.py` 삭제. source 값 규약 정합(document→book, llm→ai_prereq). ISSUE-015 선반영(청크 `embed_batch(purpose="passage")`, 개념은 query). int id 생성순 의존은 `(part_index, chunk_index)` 문서순/created_at으로 대체. diagnostic의 세션별 mastery는 정본 `concept_mastery`(user×concept)에 **업서트**로 흡수(유일한 로직성 변경).
- **스쿼시 단독 금지 준수**: 단일 0001 재작성 대신 우리 계보 head 위 `0015_parsing_contract_fields.py` 추가. parsing 계보 versions 12개는 트라이얼 브랜치에서만 제거(이중 head 방지).
### 한 일
- 커밋 `3a36bb0`(1단계) · `a3d573e`(2단계, 33 files +677/−1288). 모델 유니온: documents(+refined_elements/profile/error), doc_chunks(+element_from/to·heading·part_index), concepts(+embedding HALFVEC4096·source_anchor·source_chunk_id·created_at, key는 잠정 nullable — 섭취 시점에 없고 seed build가 채움, 합의 후 NOT NULL 복원), concept_mastery(+session_id·answered_count·resolved·locked), 신설 diagnostic_sessions/questions(UUID). api.py에 documents/diagnostic 라우터 활성화.
### 변경 파일
worktree `~/metalearn-mergecheck` 전반(backend features/documents·diagnostic·seed·materials·learning models, alembic 0015, api.py, solar.py, config.py, main.py, docker-compose.trial.yml)
### 결과
**ISSUE-001을 UUID 정본으로 풀면 서비스가 실제로 구동됨을 실증.** 업로드→정제→씨앗→진단→placement→학습 백엔드 체인이 한 코드베이스에서 공존·동작.
### 검증 (실행한 명령·결과)
- AST 전체 PASS / 컨테이너 `import app.main`+`configure_mappers()` PASS (재검증 포함 2회)
- 빈 DB에서 `alembic upgrade head` 0001→0015 전체 적용 PASS
- 학습 서빙 무회귀: `dev_seed_serving` → generate → ready → 정답 스트립 봉투 PASS
- 실 Solar: `POST /diagnostic/start`(세션·mastery 업서트·문항 생성) / answer(BKT 갱신) / `POST /seed/:id/build`(트리·floor/ceiling·enrollment) PASS
- 미실행: 실 PDF `/documents/upload` E2E(비용) — 실데이터 1회 권장
### 다음 액션
- parsing 팀원 리뷰: 이 브랜치를 참고용(A) 또는 병합 베이스(B)로 쓸지 결정 → **스쿼시(단일 0001)는 반드시 동시 진행**
- 합의 필요 잔여: concepts.key NOT NULL 복원 시점 / concept_mastery.answered_count 파생값 원칙 충돌(추후 attempts 집계로) / 재진단 시 학습 mastery 리셋 정책 / 이슈 번호 체계 충돌(양측 016·017 각자 사용)

---

## 2026-07-07 (세션11) — Claude (Fable 5) — 생성 파이프라인 성능 튜닝 (34.5s→11.2s)
### 사용자 요청
parsing 통합 대기 중 우리가 할 수 있는 작업으로 성능 튜닝 제안 요청 → 제안 1~4 묶음(병렬화·json_mode·커넥션 재사용) 승인·실행. 정본 문서 규칙 준수 + 최초 제안서(확증편향_도전제안서.pdf) 대조 요청.
### 추론·결정 (왜 이렇게 했나)
- **병목 진단**: 챕터 생성이 절 순차 루프 + 절 내부 LLM 콜 전부 직렬(임베딩1 + 생성1~2 + faithfulness 블록당 1콜 직렬) ≈ 챕터당 직렬 ~30콜. 게다가 `SolarClient._post`가 콜마다 `httpx.AsyncClient` 새로 생성(TLS 핸드셰이크 반복).
- **절 병렬화 구조**: sync SQLAlchemy Session은 태스크 간 동시 사용 불가 → 3단계 파이프라인으로 재구성: [수집(직렬 DB·임베딩)] → [생성(절 단위 `asyncio.gather`, 순수 계층만)] → [저장(직렬 DB)]. 코딩 원칙 ①(순수 계층 분리) 덕에 generator가 DB 비의존이라 깔끔히 분리됨.
- **faithfulness 병렬 vs 배치 1콜**: 배치는 파싱 실패 시 관대통과 정책 때문에 전 블록 무검증 통과 리스크 → 검증 강도를 유지하는 gather 병렬 선택.
- **429 방어**: 병렬화로 동시 콜 증가 → Solar 클라이언트에 프로세스 전역 세마포어(동시 8) 신설. 백오프 sleep 동안에도 슬롯 유지(429 시 신규 유입 억제 의도).
- **json_mode**: Solar `response_format=json_object`로 파싱실패→재생성(콜 2배) 확률 축소. 방어 파싱(`parse_llm_blocks`)은 이중 안전망으로 유지.
- 부분 성공 허용: 한 절 생성 실패 시 해당 절만 스킵(로그), 나머지 저장 — 기존 "전체 실패" 정책보다 완화(total=0일 때만 failed).
### 한 일
- `generator.py`: 게이트1(코어스+근거) 통과 후보 수집 → faithfulness `asyncio.gather` 동시 판정 → 순서(order) 보존 저장. 생성 콜에 `json_mode=True`.
- `service.py`: `_generate_one_section` → `_prepare_generation_input`(DB 수집) 분리 + `run_chapter_generation` 3단계 파이프라인화(`gather(..., return_exceptions=True)`).
- `solar.py`: 공유 `AsyncClient`(lazy, keep-alive) + `aclose()` + 전역 세마포어(8).
- `main.py`: lifespan에서 `solar_client.aclose()`.
### 변경 파일
`learning/generator.py` · `learning/service.py` · `core/llm/solar.py` · `main.py` (커밋 `30f9977`)
### 결과
챕터 JIT 생성 크리티컬 패스가 "임베딩+생성+faithfulness 1회분" 수준으로 단축.
### 검증 (실행한 명령·결과)
- 스텁 LLM(0.3s 지연) 단위검증: 1절 1.5s→0.6s(동시4콜)·5절 7.5s→0.6s(동시20콜), json_mode 전달·mcq 폐기 정책·order 연속성·verified 전부 assert 통과.
- 실환경 E2E(Docker+PostgreSQL+실제 Solar, `dev_seed_serving` 4절): **before 34.5s → after 11.2s (3.1배)**. before는 `git stash`로 구코드 복원 후 동일 조건 측정. 생성 13~14블록 동등, 정답 스트립 NO_LEAK 확인.
- 측정 시 주의(재발 방지): `dev_seed_serving.py`는 멱등이지만 매번 새 UUID 재생성 → 측정 스크립트에 ID 하드코딩 금지(시드 stdout 파싱으로 해결했음). metalearn-integration 스택이 5432/8000 점유 → compose override(`ports: !reset`)로 회피.
### 다음 액션
- ISSUE-018(프리페치·채점 타임아웃 분리)는 후속.
- 같은 날 이어서: parsing 병합 트라이얼(세션12) — 사용자 지시로 우선순위 변경.

---

## 2026-07-07 (세션10) — Claude (Opus 4.8) — RAG 임베딩 검색 + 복습(9단계) 배선
### 사용자 요청
교육플랫폼=정확성 우선 → RAG 강화(ISSUE-004). 이어서 복습(9) 배선. + 진행 기록.
### 추론·결정
- **RAG 비대칭 임베딩**: 개념=query / 청크=passage(Solar dual model). parsing 현황 확인 결과 청크를 query모델로 색인·개념도 임베딩함 → 병합 계약(ISSUE-015): parsing이 청크를 passage로(1줄), 우리는 `concepts.embedding` 소비. LLM은 service(async), DB쿼리는 repo 유지.
- **복습**: sm2·record_attempt(kind=review)는 이미 있고 라우터만 스텁 → due/answer/schedule 엔드포인트만 추가. answer는 record_attempt(kind=review) 위임(중복 로직 없음).
### 한 일
- RAG: `repo.search_concept_chunks`(pgvector cosine + 키워드 폴백), service에서 개념 query 임베딩, 픽스처 청크 passage 임베딩(테스트용)
- 복습: `review/{schemas,service,router}.py` + `repo.get_due_masteries/get_schedule_masteries/get_review_block`, 프론트 `features/review/{api,queries}` + Library 복습 도래 배지
### 변경 파일
- 백엔드: `learning/repository.py`(RAG검색·복습조회), `learning/service.py`(RAG질의), `review/{schemas,service,router}.py`, `dev_seed_serving.py`(청크임베딩)
- 프론트(integration): `features/review/{api/getReviewDue,queries/useReviewDue}`, `pages/LibraryPage`(배지)
### 결과
- 생성 근거 검색이 의미 기반으로 정확해짐. 복습 루프(도래→인출→SM-2 재스케줄) 서버측 완성 + 프론트 진입 배지.
### 검증 (실환경: Docker + PostgreSQL + Solar)
- RAG: 키워드 "트랜잭션" 없는 의미 질의 → 트랜잭션 청크 TOP1 ✅
- 복습: 정답 후 next_due 설정 → 과거로 조작 → `/review/due` dueCount=1(mcq kind=review) → `/review/answer` 정답 → 2026-07-12 재스케줄 → due 해소(0), `/review/schedule` 미래 표시 ✅
### 커밋/푸시
- `feat/backend-ai-core`: `054bdc6`(RAG)·`41b8398`(복습) → push
- `feat/integration-test`: `fdec9e5`(RAG)·`f21fbd2`(복습+배지) → push
### 다음 액션
- 복습 답변 화면(ReviewGateModal 흐름) 프론트 완성 / faithfulness 위험도 차등 / parsing 병합(ISSUE-001)

---

## 2026-07-06 (세션9) — Claude (Opus 4.8) — 프론트 배선(통합 worktree) + 잠금 서버화 + faithfulness 게이트
### 사용자 요청
프론트 팀원 ~3주 부재 → 프론트 마무리 인수. dev+우리 백엔드 조립 테스트 브랜치 → 프론트 mock→실 API 배선 → 원칙 재검증 → faithfulness 강화.
### 추론·결정
- **통합 worktree**(`feat/integration-test`): `front-learning` 프론트 + `backend-ai-core` 백엔드 오버레이(경로 disjoint). 원래 트리·materials WIP 무손상. **데모/미리보기 브랜치(병합 아님)**, dev 병합은 ISSUE-001 후.
- **아키텍처 원칙 재검증(README §2·§3)**: 프론트=봉투 조립+**서버상태 미러**, 판단은 전부 백엔드. 1차 배선에서 진행/완료/잠금을 클라 계산한 위반을 발견→수정(트리 progressStatus/locked 미러). `locked`는 백엔드가 계산해 트리에 실음(순차: 완료됐거나 이전 절 전부 완료면 열림).
- **mcq answerIndex 무유출 유지** + 채점 후 `reveal`로 정답/해설 공개 → 프론트 라운드트립 채점.
- **faithfulness(ISSUE-003)**: 블록 단위 Solar 근거 대조. net-additive(관대 폴백)라 생성 붕괴 없이 hallucination만 필터.
### 한 일
- 프론트 배선(integration): 책장/학습/분석 페이지 실 API, 블록 라운드트립(mcq/cloze/explainBack), api/query 계층, 살아있는 커리큘럼 UI(선수결손 배너·복귀·AI튜터 적응형 코멘트), axios 임시 인증헤더
- 백엔드: `SectionNode.locked` 서버계산(curriculum), `generator.check_faithfulness` + 게이트2 배선
- 문서: `docs/PROJECT_STATUS.md`(공유용 현황·평가) 신규
### 변경 파일
- 프론트(integration): `pages/{Library,Learning,Analysis}Page`·`learning/AiTutorPanel`·`blocks/{types,Mcq,Cloze,ExplainBack}`·`shared/api/client`·`features/{library,learning,analysis}/{api,queries}/*`
- 백엔드: `curriculum/{schemas,router}.py`(locked), `learning/generator.py`(faithfulness), `docs/PROJECT_STATUS.md`
### 결과
- 프론트가 우리 백엔드 로직(생성·검증·채점·진행·잠금·국소화·선행삽입)을 화면까지 관통. 아키텍처 원칙 정합. faithfulness로 생성 신뢰성↑.
### 검증 (실환경: Docker + PostgreSQL + Solar)
- 책장/학습/분석 실 API 응답, mcq 라운드트립(reveal), cloze segments, 잠금 서버계산(정규화 완료→트랜잭션 locked) ✅
- faithfulness: 근거일치 주장 supported=True / 지어낸 주장 supported=False ✅
### 커밋/푸시
- `feat/backend-ai-core`: `1f0c0bf`(locked)·`d4f6794`(status doc)·`6f769b0`(faithfulness) → push
- `feat/integration-test`: `02ac6b0`(배선)·`9e09cbe`(살아있는 커리큘럼 UI)·`ca04afd`(faithfulness) → push (팀 공유)
### 다음 액션
- faithfulness 위험도 차등 / RAG(ISSUE-004) / 복습(9) 배선 / parsing 병합(ISSUE-001)

---

## 2026-07-06 (세션8) — Claude (Opus 4.8) — ISSUE-014 우리측 봉투 계약 정합(프론트 연동 준비)
### 사용자 요청
프론트랑 딱 연동되게 우리쪽 먼저 정합(ISSUE-014 우리측 4개). dev엔 아직 안 올림.
### 추론·결정
- 프론트(feat/front-learning)의 봉투 타입/렌더러가 기대하는 모양에 우리 서빙을 맞춘다. 단 **mcq answerIndex는 우리 원칙(무유출·서버채점)이 이기고**, 대신 **채점 후 공개(reveal)**로 프론트가 정답/해설을 라운드트립으로 표시하게 한다(프론트는 클라 answerIndex 의존 제거 필요 — 프론트측 몫으로 남김).
- cloze는 프론트 `segments[]`가 렌더에 낫고 정답 제거와도 자연스러움 → serializer가 `{{blank}}` 마커 기준 변환.
### 한 일
- 봉투에 `kind` 추가(`BlockEnvelope`+`to_envelope`) — attempts.kind 그대로 방출
- `SectionBlocksResponse`에 `id`/`title` 추가(프론트 SectionPayload 계약), 기존 sectionId/variant 유지
- serializer cloze: `text`+`blanks` → `segments[]`(text/blank 교차, 정답 없는 blank). `strip_answers`에 분기 + `_cloze_to_segments`
- 채점 응답 `RevealOut` 신설 + `AttemptResponse.reveal`: mcq→answerIndex+explanation, cloze→blanks (채점 후 공개, 유출 아님)
- 픽스처에 cloze 블록 편입(tracked=False), 정리에 `learning_cursor` 삭제 추가(세션6 신규 테이블 FK)
### 변경 파일
- `learning/schemas.py`[kind·id/title·RevealOut], `learning/serializer.py`[cloze segments·kind·docstring], `learning/service.py`[serve_section id/title·`_build_reveal`·reveal], `dev_seed_serving.py`[cloze·커서 정리]
### 결과
- 우리 서빙 봉투가 프론트 계약과 정합(mcq strip은 reveal로 보완). 프론트가 mock 걷어내고 붙일 준비 완료.
### 검증 (실환경: Docker + PostgreSQL)
- `GET /sections/:id` → `id`/`title=정규화` · 봉투 `kind=learn` · mcq **answerIndex 유출 False** · cloze `segments=[{text},{blank},{text}]`(정답 없음) ✅
- `POST /attempts` mcq 오답 → `reveal={answerIndex:1}` 공개 ✅
### 다음 액션
- 프론트측(ISSUE-014): McqBlock/ClozeBlock 라운드트립 채점으로(클라 answerIndex 제거), reveal로 정답/해설 표시
- 남은 우리 엔드포인트: review/*·map·progress·connections + API.md에 우리 신규 반영
- 통합 브랜치 조립(우리 backend + front-learning frontend) — 배선 착수 시

---

## 2026-07-06 (세션7) — Claude (Opus 4.8) — 병합 안전(API 계약 정합) 착수 + dev/front-learning 분석
### 사용자 요청
프론트는 팀원이 진행 → 병합(parsing+프론트+우리) 안전 작업으로. dev 현황 확인 → API 계약 정합. + 새 브랜치 `feat/front-learning` 분석. **(중요) 프론트 팀원 ~3주 부재 → 프론트 마무리를 우리가 할 수도 있음.**
### 추론·결정 (병합 3-이음새)
- **① backend-ai-core → dev**: 낮은 위험. dev 백엔드는 스켈레톤(`learning/models.py`=LearningItem 20줄), `0001`은 우리와 동일 → 우리 마이그 0002~0014가 깨끗이 올라감. 우리 vs dev backend = +3763/−88(거의 additive).
- **② frontend(dev) ↔ 우리 API**: 실질 위험. API.md(프론트 계약)와 우리 실 API가 양방향 드리프트. → **여기부터**(솔로 가능, 프론트 병합 직결).
- **③ backend-ai-core ↔ parsing**: 진짜 블로커(ISSUE-001, 단독 금지).
- 프론트 현황: 페이지 껍데기 거의 완성(Landing/Auth/Profile/Library/Analysis/Learning/Settings/Create), API 클라이언트(axios) 있음. **대부분 mock, 배선 초기**. `useGenerate`가 topic 기반(우리 chapterId 기반과 불일치), baseURL에 `/api` 없음.
- `feat/front-learning`(dev+1커밋): 학습 봉투 렌더러(registry) — 아키텍처는 우리와 정합(같은 5 type·봉투·source 배지·onAnswer), **그러나 data 모양 불일치**(ISSUE-014). 아직 mock.
### 한 일
- 전 브랜치(dev/parsing/front-learning) 실물 분석 → 병합 3-이음새·계약 드리프트 도출
- **우리측 프론트-필요 엔드포인트 2개 구현·검증**:
  - `GET /courses` (책장 목록) — 진행률+개념수+마지막활동(MAX attempts.created_at 계산값)
  - `GET /courses/:id/mastery` (메타인지) — 개념별 상태 + 상태별 요약
- `feat/front-learning` 봉투 계약 대조 → ISSUE-014 도출
### 변경 파일
- `curriculum/schemas.py`[CourseListItem/Response·ConceptMasteryItem·MasteryResponse], `curriculum/repository.py`[책장 집계 4함수·get_concepts_of_course], `curriculum/router.py`[GET /courses·GET /courses/:id/mastery]
### 결과
- 프론트 Library·Analysis 페이지에 바로 대응하는 백엔드 엔드포인트 확보(mock 걷어내면 붙음).
### 검증 (실환경: Docker + PostgreSQL)
- `GET /courses` → `{conceptCount:6, totalSections:5, completedSections:0, progress:0}` ✅
- `GET /courses/:id/mastery` → 개념 6개 + 상태별 요약(200) ✅ (초기 KeyError는 시드 CID 빈 404였음, 실 CID로 정상)
### 다음 액션
- 남은 프론트-필요 우리 엔드포인트: `review/*`(sm2 로직만 있음)·`/map`·`/progress`·`/connections`
- 우리 신규(placement·cursor·attempts의 cause/prerequisite/resume)를 API.md에 반영
- ISSUE-014 우리측 4개 정합(kind·section title/id·cloze segments·채점응답 정답+explanation)
- **프론트 3주 부재 → 프론트 마무리 착수 여부 결정 대기**

---

## 2026-07-06 (세션6) — Claude (Opus 4.8) — 학습 커서(복귀 자동화) 구현·검증
### 사용자 요청
프론트 연동은 나중, 서버 학습 커서 먼저.
### 추론·결정
- 선행 우회 후 **원래 절 복귀 지점**을 서버가 알아야 함 → (유저×코스) 커서 + **복귀 스택(LIFO)**. 중첩 선행(선행의 선행) 대응.
- 진단/판정과 무관한 '어디로' 상태라 `section_progress`와 분리된 새 테이블 `learning_cursor`(우리 도메인, 새 마이그 0014). enrollments(진단이 채움)를 안 건드림 → 경계 유지.
- push=선행 삽입 시(현재 절→스택, 커서=선행 절), pop=절 완료 시(커서가 그 절이면). 복귀 지점은 attempt 응답 `resumeSectionId` + `GET /courses/:id/cursor`로 표면화. 실제 라우팅은 프론트.
### 한 일
- 모델 `LearningCursor` + 마이그 `0014_learning_cursor`
- repo: `get_cursor`/`push_and_enter`/`pop_return`(JSONB 스택 재할당)
- service: `_ensure_prerequisite_target`에 push 배선, `record_attempt` [6b]에 완료→pop, `get_cursor`
- 스키마: `AttemptResponse.resume_section_id` + `CursorResponse`, 라우터 `GET /courses/:id/cursor`
### 변경 파일
- `learning/models.py`[LearningCursor], `alembic/versions/0014_learning_cursor.py`[신규], `learning/repository.py`[커서 3함수], `learning/service.py`[push/pop/get], `learning/schemas.py`[Cursor/resume], `learning/router.py`[GET cursor]
### 결과
- 살아있는 커리큘럼 내비 루프 완성(서버측): 실패→국소화→선행 삽입+커서 push→선행 학습→완료→pop→원래 절 복귀.
### 검증 (실환경: Docker + PostgreSQL, alembic head=0014)
- 선행 삽입 후 `GET /cursor` → `current=선행절, returnDepth=1` ✅
- 선행 절 tracked 블록 전부 통과 → attempt 응답 `resumeSectionId=정규화절`, 커서 `current=정규화절 returnDepth=0` ✅
- (테스트 중 오염 블록 1개로 완료 지연 → 원인은 데이터, pop 로직은 정상 확인)
### 다음 액션
- 프론트 라우팅 연동 / cause=content 처방(보충) / ISSUE-013 placement 좁히기(병합 시)

---

## 2026-07-06 (세션5) — Claude (Opus 4.8) — ISSUE-002 선행 삽입 실행부(cause 구동) + 경계·placement 정의 기록
### 사용자 요청
ISSUE-002 바로. + placement가 정확히 뭔지 설명 추가. + 경계 인식: 진단평가=parsing, "진단 후→커리큘럼 생성"부터가 우리.
### 추론·결정
- **경계 확정(ISSUE-013)**: 진단평가·수준 판정=parsing 산출물. `initialize_placement`는 판정 계산이 아니라 *수령·기록·킥오프*여야(병합 시 좁힘). localization은 수업 중 인출 기반이라 진단 아님 → 우리 영역 유지.
- **placement 정의**를 코드 docstring에 명시(반편성: floor=시작점/ceiling=목표 → mastered/todo/locked).
- **ISSUE-002 트리거 = cause 구동**: Router의 거친 consecutive_wrong이 아니라 `cause=prerequisite`(국소화)일 때만 삽입 → content면 삽입 안 함(Router×cause 자연 흡수). **틀렸을 때만**(성공 시 미개입).
- **범위**: 서버는 삽입·표면화까지(멱등). JIT 생성/복귀는 프론트가 반환된 대상으로(서버 학습 커서는 후속).
- 코스가 유저별(courses.user_id)이라 챕터도 사실상 유저별 → 코스 단위 삽입이 타 유저에 안 샘.
### 한 일
- `initialize_placement` docstring에 placement 정의 + 경계 명시
- repo: `find_section_by_concept`(멱등 판단)·`insert_prerequisite_chapter`(origin=prereq, 현재 앞 order-5, pending)
- service: `_ensure_prerequisite_target` + `record_attempt` [4c]에 cause 구동 배선(응답 `prerequisite` + meta `prereqChapterId`)
- 스키마: `PrerequisiteTargetOut` + `AttemptResponse.prerequisite`
- 픽스처 버그 수정: 섹션 add_all 후 `flush()` 누락 → `blocks.section_id` null(세션3부터 잠복, section_id 첫 사용인 지금 발현). dev 스크립트 문제, 제품코드 아님
### 변경 파일
- `learning/repository.py`[선행 조회·삽입], `learning/service.py`[placement docstring·`_ensure_prerequisite_target`·[4c]], `learning/schemas.py`[`PrerequisiteTargetOut`], `dev_seed_serving.py`[flush 수정]
### 결과
- 살아있는 커리큘럼 루프가 서버측에서 닫힘: 실패 → 국소화(blame) → 선행 챕터 삽입 → 대상 표면화 → 멱등.
### 검증 (실환경: Docker + PostgreSQL, parsing 규약 픽스처)
- 오답2 → `cause=prerequisite`(blame=관계대수 depth2) → `prerequisite={관계대수, created:true, genStatus:pending}` ✅
- chapters: `[선행] 관계대수`(origin=prereq, order_index=5 현재 챕터 앞, 절→relational-algebra) 생성 ✅
- 오답3 → 멱등 `created:false`, 동일 챕터 재사용(중복 삽입 없음) ✅
### 다음 액션
- 프론트 연동: `prerequisite` 대상으로 라우팅→`POST /chapters/:id/generate`→학습→원래 절 복귀
- 후속: 서버 학습 커서(복귀 자동화) / cause=content 처방(보충 블록 reset) / ISSUE-013 placement 좁히기(병합 시)

---

## 2026-07-06 (세션4) — Claude (Opus 4.8) — 지식그래프 방향 규약 확정(parsing 채택) + placement·localization 재정합
### 사용자 요청
씨앗에 선수지식을 계층으로 넣으면 다운스트림이 편해지지 않나? → (발견 공유) → **parsing 그래프 규약에 맞춰줘**.
### 추론·결정
- 사용자 직관(씨앗에 선수지식 내장)은 **이미 합의 설계**이자 내 placement/localization의 소비 대상. 그런데 확인해보니 **생산자(parsing) ↔ 소비자(내 session2/3)의 그래프 방향이 정반대**(ISSUE-012):
  - parsing: 엣지 `from=의존→to=선수`, `depth 클수록 선수(스파인=0)`, 진행축=커리큘럼 순서
  - 내 코드: 엣지 `from=선수→to=의존`, `depth 작을수록 기초`, depth=진행축
  - → 실씨앗 붙이면 placement 뒤집힘·blame 반대. 내 session2/3 E2E가 통과한 건 **자기 픽스처(내 규약)** 라서였음(통합 검증 아님).
- **결정: parsing 규약 채택**(생산자+진단 BKT가 이미 그 규약, 코드량↑ / 내 소비자는 신생·미통합이라 뒤집기 비용 최소). 방향 규약을 `docs/GRAPH_ORIENTATION_CONTRACT.md`로 확정.
- 정본 `SCHEMA.md`는 엣지 방향·depth 방향을 미규정 → 이 문서가 공백을 채우는 계약.
### 한 일
- 규약 문서 `docs/GRAPH_ORIENTATION_CONTRACT.md` 신규(확정본)
- localization 정합: `get_prerequisite_ids`를 `to WHERE from==X`로 뒤집음, blame을 **최대 depth**(최상류=근본)로, 미학습 선행 P(known) 기본 0.5→**0.0(gap)**
- placement 정합: 진행축을 depth→**커리큘럼 순서**로. `classify_placement(position, floor/ceiling_position)`, `repo.get_curriculum_order`(섹션 매핑 개념만), 섹션 없는 순수 선행은 미시딩
- 픽스처를 parsing 규약으로 재구성(스파인 4섹션 + 선행 2개 depth 1·2, 엣지 의존→선수) + 재실행 FK 정리 보강(blocks 먼저 삭제)
### 변경 파일
- `docs/GRAPH_ORIENTATION_CONTRACT.md`[신규]
- `learning/repository.py`[선행조회 방향·`get_curriculum_order`], `learning/localization.py`[blame max depth], `learning/mastery.py`[classify_placement 순서축], `learning/service.py`[placement/localize 정합], `dev_seed_serving.py`[parsing 규약 픽스처]
### 결과
- 소비자(placement·localization)가 parsing 그래프 방향에 정합. 병합 시 방향 재작업 불필요.
### 검증 (실환경: Docker + PostgreSQL, parsing 규약 픽스처)
- placement → `{seeded:4, mastered:1(개요), todo:2(정규화·트랜잭션), locked:1(인덱스)}` — 커리큘럼 순서 버킷 ✅ (순수 선행은 미시딩)
- localize 오답1 → `hold`; 오답2 → `prerequisite` **blame=관계대수(depth2)** — 두 직접선행{DB기초 d1, 관계대수 d2} 중 **더 깊은(근본) 쪽** 선택 = 엣지 방향+depth 방향 뒤집기 동시 검증 ✅
- 두 선행 강화 후 오답 → `content`(대상 P=0.17) ✅
- ※ 이건 parsing 병합 여부와 무관 — 규약을 미러링한 UUID 픽스처로 **소비자 로직**을 병합 전 검증(ISSUE-001 미해결로 실 parsing 산출물은 아직 못 돌림)
### 다음 액션
- Router×cause 연결 / ISSUE-002 선행 삽입 실행부(blame 개념 → prereq 챕터)
- 병합 시 parsing depth=DAG 최장경로 계산 확인 + `blocks.concept_id` CASCADE 정리

---

## 2026-07-06 (세션3) — Claude (Opus 4.8) — ISSUE-010 원인 국소화 1차(BKT×DAG) 구현·검증
### 사용자 요청
parsing 산출물을 바로 연동 가능하게 → ISSUE-010(수준 체크 본체) 바로 진행.
### 추론·결정 (왜 이렇게 했나)
- **비침습 슬라이스**: 기존 ELO-lite `strength` 루프는 그대로 두고, **원인 국소화를 파생 계산 레이어로 얹음**(작동 중인 인출 루프를 갈아엎지 않음).
- **BKT×DAG 결합**: 대상 P(known)은 attempts 정오 시퀀스를 BKT로 접어 추정하되, **P(L0)를 선행들의 P(known)으로 결합**(weakest-link) — 선행 약하면 사전확률↓ → 실패가 "예상된 것" → blame이 선행으로 흐름.
- **선행 P(known) 프록시 = `concept_mastery.strength`**(placement가 이미 시딩·유지). 선행별 BKT 재추정은 후속(쿼리 폭증 회피).
- **엣지 규약 확정**: `from`(선행)→`to`(의존), kind=prerequisite. 대상 X의 선행 = {e.from : e.to==X}. (인덱스 `ix_concept_edges_to`가 이 조회에 최적) **신호는 엣지로만 전파**(직접 선행만).
- **단일 임계 금지**: (대상 P·시도수·선행 P) 조합. 시도<2면 `hold`(판단 보류)로 오탐 방지. 선행 약함→`prerequisite`(최상류=최저 depth 약선행 blame), 선행 충분·대상 약함→`content`. 오개념은 서술채점 근거 필요 → 훅만(`misconception_signal`), 후속.
- **파생값 저장 안 함 원칙 준수**: P(known)은 attempts에서 매번 계산, 스키마 변경 0. cause는 `attempts.meta`에 감사 로그로 기록(오답노트 스키마=ISSUE-009 별도).
### 한 일
- 순수: `learning/bkt.py`(BKT 4파라미터 + `p_l0_from_prereqs` + `estimate_p_known`), `learning/localization.py`(`Cause` + `localize` 조합 규칙)
- repo: `get_prerequisite_ids`/`get_concept_depths`/`get_strength_map`/`get_concept_outcomes`
- service: `_localize_cause` + `record_attempt` [4b]에 배선(응답 `cause` + `attempts.meta`에 기록)
- 스키마: `CauseOut` + `AttemptResponse.cause`
- 픽스처: 선행 엣지(db-basic→normalization) + 채점 mcq 블록 추가
### 변경 파일
- `learning/bkt.py`[신규], `learning/localization.py`[신규]
- `learning/repository.py`[+선행/정오/강도/depth 조회], `learning/service.py`[+`_localize_cause` 배선], `learning/schemas.py`[+`CauseOut`], `dev_seed_serving.py`[엣지+mcq]
### 결과
- 실패 원인을 **선수결손 / 본문결손 / 판단보류**로 국소화하고 blame 선행을 지목 — ISSUE-002(선행 삽입) 실행부에 넘길 대상이 생김.
### 검증 (실환경: Docker + PostgreSQL, 실제 attempts)
- 오답1회 → `cause=hold`(시도1<2) ✅
- 오답2회(선행 strength=0) → `cause=prerequisite`, blame=db-basic(P=0.00, depth2) ✅
- 선행 strength=0.8로 강화 후 오답 → `cause=content`(대상 P=0.17) ✅ — Router의 거친 "prerequisite"와 달리 정확히 본문결손으로 분리
- `attempts.meta`에 cause/blameConceptId 영속 확인(hold/prerequisite/content 3행) ✅
### 다음 액션
- **Router×cause 연결**: 현재 `next_action`은 consecutive_wrong으로만 prerequisite 판단 → cause가 `content`면 선행 삽입 대신 보충 유지하도록 cause를 Router 입력으로. (지금은 독립)
- **ISSUE-002 실행부**: cause=prerequisite의 blame 개념 → `chapters(origin='prereq')` 동적 삽입
- 후속 정밀화: 선행별 BKT 재추정 / 오개념 신호(explainBack rubric) / 콜드스타트 사다리(confidenceCheck·프로브·클러스터 warm start) / depth=DAG 최장경로 실계산 의존
- parsing 팀원과 ISSUE-001 정합 목록 합의(정본 UUID 스쿼시)

---

## 2026-07-06 (세션2) — Claude (Opus 4.8) — 상류 이음새 검증(정본=UUID 확정) + placement 시딩 구현 착수
### 사용자 요청
"metalearn 어디부터 구현?" → 담당 재확인(커리큘럼 생성 + 사용자 수준 체크). dev(프론트)·parsing(상류) 작업현황 확인 → 우리 브랜치 중점 결정 → **상류 이음새 검증**부터 착수. PK 타입 분기는 dev docs(정본 스키마)로 판정.
### 추론·결정 (왜 이렇게 했나)
- **parsing 진척**: 씨앗 산출물 계약(`d3217a8`, ISSUE-017)까지 나옴 — `chapters`/`sections`/`concepts.key`/`enrollments.floor·ceiling·purpose`. 즉 하류 서빙의 **실입력이 이제 존재**. 그 앞단(정제·섹셔닝·개념추출·doc_chunks 임베딩·BKT 진단+원문근거)도 머지됨.
- **3자 대조로 PK 정답 확정**: `dev:docs/SCHEMA.md`가 **팀 정본**이고 전 테이블 `uuid PRIMARY KEY DEFAULT gen_random_uuid()`. → **PK 정답 = UUID**. 내 브랜치(A+B 계층)는 정본과 거의 완전 일치. **갈라진 쪽은 parsing(Integer)** — 이는 parsing seed가 스스로 "concept_mastery는 UUID 이관 시점에"로 미뤄둔 예고된 부채.
- **이음새 결론**: "내가 parsing에 맞춰 고친다"가 아니라 "parsing이 정본(UUID)으로 올라오면 붙는다". parsing에 넘길 정합 목록: PK Integer→UUID / `enrollments.*_concept_id`→`*_concept` + `diag_status`·`diag_q_count` / `concepts.key` NOT NULL+UNIQUE / `concepts.source` `'document'`→`book|ai_prereq`.
- **정본 대비 내 브랜치도 뒤처진 곳**: `courses`가 정본은 `document_id` 제거+`course_documents` N:N(다중자료). 내·parsing 둘 다 단일 `document_id` → ISSUE-011 신설. `users` 소셜(provider/provider_uid) 미반영은 기존 ISSUE-005.
- **솔로 착수 지점 선정**: `floor/ceiling` placement를 서빙이 **아직 안 읽음**(grep 소비지점 0) + `concept_mastery`는 첫 attempt 때 lazy 생성뿐. → **진단 종료(floor/ceiling 확정) 시점에 concept_mastery를 depth 기반으로 시딩**하는 "수준 체크 진입점"을 구현. BKT×DAG 정밀화는 ISSUE-010으로 후속.
### 한 일
- 전 브랜치 실물 대조(parsing/dev git + 모델 필드 단위) → 3자 대조표·정합 목록 도출
- placement 시딩 구현: 순수(`mastery.classify_placement`) + repo(enrollment/course concepts/멱등 bulk seed) + service(`initialize_placement`) + 라우터(`POST /courses/{id}/placement`, 진단종료 핸드오프용 임시 노출) + Enrollment.purpose 정본정합(마이그 0013) + 픽스처 확장
- Docker E2E로 3버킷 시딩·멱등성·트리 반영 검증(아래 검증란)
### 변경 파일
- `learning/mastery.py` [+`classify_placement`/`PlacementSeed` 순수 판정]
- `learning/repository.py` [+`get_enrollment`/`get_course_concepts`/`seed_mastery_if_absent`(멱등)]
- `learning/service.py` [+`initialize_placement` 오케스트레이션]
- `learning/schemas.py` [+`PlacementResponse`]
- `learning/router.py` [+`POST /courses/{id}/placement` 임시 노출]
- `learning/models.py` [Enrollment +`purpose` — 정본 정합]
- `alembic/versions/0013_enrollment_purpose.py` [신규 — enrollments.purpose]
- `dev_seed_serving.py` [depth 4개 개념 + Enrollment(floor/ceiling) + FK안전 정리]
### 결과
- **이음새 검증 산출물**: 정본=UUID 확정, 우리 쪽 정합, 블로커=parsing Integer PK + 정합 목록(단독 금지 — parsing 팀원 대기).
- **placement 시딩 완성·검증**: 진단 floor/ceiling → concept_mastery depth 기반 3버킷 시딩. 수준 체크 진입점 확보.
### 검증 (실환경: Docker + PostgreSQL, alembic head=0013)
- `alembic upgrade head` 0013까지 정상 / 백엔드 클린 기동(import 에러 없음) ✅
- `POST /courses/:id/placement` → `{seeded:4, mastered:1, todo:2, locked:1}` — 기대값 정확 일치 ✅
- concept_mastery 실제 행: 집합개념(depth1<floor2)→mastered 0.85 / DB기초(floor)·정규화(ceiling)→todo / 트랜잭션(depth7>ceiling)→locked ✅
- 멱등성: 재호출 → `{seeded:0, skipped:4}` 기존 상태 보존 ✅
- `GET /courses/:id` 트리에 masteryStatus/strength 반영 확인 ✅
### 다음 액션
- **계약 연결**: parsing 진단종료(`POST /courses/:id/diagnostic/answer`)가 종료 시 `service.initialize_placement`를 직접 호출하도록 통합(현재 임시 라우터 노출은 그때 내려도 됨) — parsing 팀원과 조율
- **ISSUE-010 (수준 체크 본체)**: placement의 depth 단일축을 BKT×DAG로 정밀화(선수지식 결손 vs 오개념 국소화)
- parsing 팀원과 ISSUE-001 정합 목록 합의(정본 UUID 스쿼시)

---

## 2026-07-06 — Claude (Opus 4.8) — 프로젝트 기억 시스템 구축 + 평가 설계 논의
### 사용자 요청
parsing/dev 브랜치 변경 확인 → 평가·맞춤 알고리즘 설계 논의 → **프로젝트 기억 시스템(`CLAUDE_CONTEXT.md`/`WORK_LOG.md`)을 과거 소급 포함해 구축**. 범위는 backend-ai-core 중심이되, 팀원·다른 LLM이 처음 봐도 이해되게.
### 추론·결정
- **기억 시스템 범위**: 내 브랜치 중심 + 자체 완결. 기존 `LEARNING_SERVING_WORKLOG.md`(커밋 `c0120cb`)는 흡수하지 않고 신규 2파일 작성. 마이그 분기는 방향 미정이라 **ISSUE-001 등록만**.
- **평가 설계 논의 결론**:
  - "모름 감지"가 "앎 감지"보다 어려운 **비대칭**(틀림의 원인이 slip/guess/결손/오개념/표현 등 다수) → **BKT의 `P(S)/P(G)`로 노이즈 흡수**. → BKT 채택이 맞음.
  - **국소화는 BKT 단독 불가**(표준 BKT는 개념 독립 가정). → **BKT×DAG 결합**: 개념 X의 `P(L0)`를 선행들의 `P(known)` 함수로(선행 낮으면 X 실패는 "예상된 것") + blame을 **최상류 낮은 선행**에 배분 → 애매하면 **성향중립 프로브**로 "맞기 시작하는 층(frontier)" 확정 → 아래→위 보충.
  - **판정 기준은 단일 임계 금지** → `(P(known)·확신도·선행 P(known))` 조합 표. "낮음+시도부족=판단 보류"로 오탐 방지.
  - **콜드스타트**: 개념별 개별 추정 대신 **개념유형/`depth_level`로 파라미터 풀링**, `P(L0)`만 그래프 기반 개별화.
  - 결손(gap, 프로브로) ≠ 오개념(misconception, 서술 채점 reframe) — 처방이 달라 측정도 분리.
- **운영 규칙**: 매 세션 시작 시 두 파일 읽기, 종료 시 기록. 에이전트가 마무리 때 "기록할까?" 선제안 허용.
- **alembic**: 도구 제거는 부적절(문제는 도구가 아니라 스키마 분기 자체). 유지하되 **통합 시점에 통합 모델로 단일 `0001_initial` 스쿼시**(prod 데이터 없어 무손실). ⚠️단독 금지 — parsing 팀원과 합의 시 동시. → ISSUE-001에 제안 방향 기록.
- **3파일 이동식 세트**: `CLAUDE_CONTEXT`+`WORK_LOG`+`AI_CORE_DESIGN_NOTES`를 세트로 타 LLM에 이관 가능. 단 (1)코드 작성 전 소스 검증 필수, (2)최신성 우선순위 WORK_LOG>CONTEXT>NOTES(코드가 최종). → CONTEXT에 온보딩 블록, NOTES에 아카이브 배너로 자기설명화.
### 한 일
- 전 브랜치 git 히스토리(31커밋)·소스 구조·설정·미완성 지점 소급 분석 → ISSUE-001~010 도출
- `docs/CLAUDE_CONTEXT.md`, `docs/WORK_LOG.md` 신규 생성
- `CLAUDE_CONTEXT`에 `## 0 온보딩 블록`(읽는 순서 + 우선순위 규칙) 추가
- `AI_CORE_DESIGN_NOTES.md`에 아카이브 배너 추가(사용자가 이 파일을 `docs/`로 이동)
- 메모리 3파일 전부 `.gitignore` 처리(원격 미공유) + ISSUE-001에 스쿼시 제안 방향 기록
### 변경 파일
- `docs/CLAUDE_CONTEXT.md` [신규 + 온보딩 블록]
- `docs/WORK_LOG.md` [신규 + ISSUE-001 갱신]
- `docs/AI_CORE_DESIGN_NOTES.md` [아카이브 배너 + `docs/`로 이동(사용자)]
- `.gitignore` [메모리 3파일 추가]
### 결과
- 이동식 메모리 3파일 세트 확립(전부 gitignore, 자기설명화). 앞으로 모든 세션이 이 규칙으로 운영.
### 검증
- `git log --all`·`find`·마이그 비교·`grep`으로 사실 확인. `git check-ignore`로 메모리 3파일 무시 확인, `sed`로 온보딩/배너 삽입 확인. **제품 코드 변경 없음**(문서/설정만) → 런타임 검증 대상 아님.
### 다음 액션
- ✅ 코딩 원칙 ③ 확정(2026-07-06, 초안 10개 그대로 승인)
- **다음 세션(2026-07-07~) 시작점 = ISSUE-002 선행 삽입 실행부 구현**: `next_action`의 `prerequisite` 신호 → `chapters(origin='prereq')` 동적 삽입(order_index 10/20/30 간격) → JIT 생성 재사용 → 유저 라우팅 → 복귀. 그 다음 ISSUE-010(원인 국소화, BKT 도입 선행).

---

## 2026-07-03 — Claude Code — 학습 서빙 + 인출 루프 구현  *(소급 재구성: 커밋 0811f13/9b4a84d/c0120cb/da2d32a + LEARNING_SERVING_WORKLOG.md)*
### 사용자 요청
"커리큘럼이 주어졌을 때 → 학습 콘텐츠를 어떻게 만들고 → 프론트 봉투로 어떻게 내보낼지" 구현. 이어서 학생 답안 제출(인출 루프)까지.
### 추론·결정
- 먼저 **dev 스키마 기준으로 백엔드 재구축**(`0811f13`) — 구 세션/RAG 코드 제거, 모델·순수 로직 재정의.
- 생성기는 **순수 계층**으로 분리(DB/ORM 비의존) → 팀 스키마가 흔들려도 로직 안 흔들림.
- **검증 게이트**: 근거 없으면 저장 자체를 안 함(dangling 방지) + 서빙 시 `WHERE verified=true` 이중 안전망. 비유는 근거 면제·`label='비유'` 강제.
- **정답 스트립**(기획에 없던 것 추가): 봉투에서 answerIndex/blanks/rubric 제거 → 채점은 서버만. `serializer._STRIP_FIELDS`로 단일 관리.
- **variant는 부분집합 필터**로 잠정(컬럼 신설 팀 미결) — full/compressed/quick, 0개면 full 폴백.
- 생성 트리거 **멱등**(조건부 UPDATE). JIT 개인화: `concept_mastery.strength`로 난이도 힌트.
- 인출: **클라 correct 무시**, 시도수/연속오답은 attempts 집계, explainBack은 Solar rubric 항목별 O/X를 서버가 비율 계산.
- FK 해석 버그(`NoReferencedTableError: users`) → `models_registry.py`(전 모델 단일 임포트) 신설로 해결.
### 한 일
- 학습 서빙 파이프라인(generator/repository/serializer/service/router) + 커리큘럼 트리(GET /courses)
- 인출 루프(grading/attempts) + next_action Router + SM-2 연결
- 임시 유저 의존성(`core/deps.py`), mock LLM 응답, `dev_seed_serving.py` 픽스처
### 변경 파일
`learning/{generator,repository,serializer,service,router,schemas,grading}.py`, `curriculum/{schemas,repository,router}.py`, `core/deps.py`, `core/llm/mock.py`, `models_registry.py`, `main.py`, `api.py`, `dev_seed_serving.py`
### 결과
JIT 생성→검증→봉투 서빙→attempts 채점→mastery/SM-2/next_action 루프 완성.
### 검증 (실환경: Docker + PostgreSQL + Solar solar-pro3)
- GET /courses 트리 ✅ / generate→ready 실제 5블록 생성(전부 verified+근거) ✅ / 정답 유출 NO_LEAK ✅ / confidence sure→quick 서빙 ✅
- mcq 오답1→supplement ✅ / 연속오답2→prerequisite ✅ / 정답→advance, strength 0→0.22 ✅ / explainBack Solar 채점 score 0.333+피드백 ✅ / 치팅(correct=true 위조) 서버 false ✅
### 다음 액션
선행 삽입 실행부(ISSUE-002) → faithfulness(003) → RAG(004) → auth(005)

---

## 2026-06-29 — (에이전트 미상) — AI 학습 코어 백엔드 + 프론트 기반  *(소급: da8fec7, 04e4e1f)*
### 한 일
- backend-ai-core 브랜치 시작: AI 학습 코어 백엔드 골격 + 프론트 기반
- `feature/front-design` 병합 → `origin/feat/backend-ai-core` 푸시(마지막 원격 반영 지점)
### 결과
이후 07-03 재구축(`0811f13`)에서 구 세션/RAG 코드는 제거됨.

---

## 2026-06-16 ~ 06-21 — (프로젝트 셋업) — 도커·폴더·스캐폴드  *(소급: c9d94a6, b3bc4ed, 597d9b5)*
### 한 일
- 초기 Docker·폴더 세팅(main) → 프론트/백 기본 골격 + 개발 환경(scaffold) → PR#2로 dev 병합
### 결과
FastAPI + PostgreSQL/pgvector + React/Vite + Docker Compose 3컨테이너 구성 확립.
