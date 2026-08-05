# MetaLearn — 문제 생성(문제 페이지) 설계

> 확정안(08-03) §6 문제 페이지의 백엔드 설계. **문제 생성 관련 변경은 이 파일에서 관리한다.**
> 입력 = 팀원 파서의 파싱 결과(목차·조각·개념·문장 앵커). 출력 = 목차별 문제은행.

---

## 0. 전제 (확정안에서 오는 규칙)

| 규칙 | 의미 |
| --- | --- |
| 파싱 직후 생성 | 진단·학습과 무관. 파싱이 끝나면 바로 문제은행을 만든다 |
| 개인화 없음 | 모두에게 같은 문제 → **한 번 생성 → 저장 → 꺼내 쓰기** 구조 |
| 데이터 격리 | 풀이 기록은 학습(숙련도·커리큘럼)에 안 섞임 → 전용 테이블 (`quiz_attempts`) |
| 근거 필수 | 모든 문항은 "📎 교재 몇 쪽 그 문장"을 보여줄 수 있어야 함 (문장 앵커 offset) |
| 기출은 참고 | 기출 문항을 복사하지 않음. **스타일·빈도만** 배움 |

---

## 1. 전체 파이프라인

```
팀원 파싱 결과 (md든 JSON이든 — 형식 미확정)
   │
   ▼ [어댑터 — 형식 확정되면 마지막에 붙임]
내부 모델 ParsedDocument (목차 → 조각 → 개념·원문·문장앵커·그림)
   │
   ▼ ① 수신·무결성 검증 (코드)
   ▼ ② 출제 대상 선별 (코드)
   ▼ ③ 기출 스타일 프로파일 (기출 문서 있을 때만 — LLM)
   ▼ ④ 예산·유형 계획 (코드)
   ▼ ⑤ 생성 — 조각당 LLM 1콜 (structured output)
   ▼ ⑥ 검증 — 기계 검사 + LLM 심판
   ▼ ⑦ 저장 — quiz_items (verified만)
   │
   ▼ ⑧ 서빙 API ←──── 여기부턴 LLM 없음, DB 조회만
프론트 문제 페이지 (기존 BlockRenderer/registry 재사용)
```

- ①~⑦은 **문서당 1회 배치**(백그라운드). 상태 `pending → generating → ready / failed`를 코스/문서에 기록, 프론트는 폴링 (학습 JIT 생성과 같은 패턴).
- 코스에 문서가 여러 개면 **문서별로 각각** 돈다 (서로 대기 없음).
- 입력 형식(md/JSON)이 미정이어도 내부 모델 한 겹으로 격리했으므로 ②~⑧ 개발은 지금 가능.

---

## 2. 단계별 설계

### ① 수신·무결성 검증

- 파서 버전 게이트 (`v3.0` 불일치 → 명시적 실패).
- 무결성 체크: 앵커 offset이 원문 범위 안인지, `raw[start:end]`가 앵커 문장과 일치하는지, 목차↔조각 매핑 실존 여부, 헤더 총계 vs 파싱 합계 대조.
- 이상 발견 시 **팀원에게 그대로 전달 가능한 에러 리포트** 생성 (`{errors[], warnings[]}`).

### ② 출제 대상 선별 — 파서는 보존, 선별은 우리 책임

파서의 임무는 원문 무손실 보존(근거 표시·커버리지 때문)이므로 정제는 출제 쪽에서 한다. 제외 대상:

- **개념이 안 걸린 문장** — 저자 인사말·광고 (예시 파일에 실재)
- **조각 근거가 없는 개념** — 선수로만 언급된 개념 (예시 파일에서 634−527=107개). 근거 📎를 못 보여주므로 출제 불가, 목록만 로그
- **`비전 필요` 그림에만 의존하는 내용** — 텍스트만으로 불완전
- **깨진 수식** (LOC 공식 등) — 계산형 금지, 정의형으로 후퇴
- **`kind=exam`(기출) 문서** — 본문 생성 파이프라인에 안 태움 (③에서만 사용)

### ③ 기출 스타일 프로파일 (기출 문서 있을 때만)

기출 파싱 결과(문항 단위)에서 코스당 1개 프로파일 추출 (문항 20개씩 묶어 LLM 콜):

```jsonc
{
  "typeDistribution": { "shortAnswer": 0.55, "mcq": 0.30, "cloze": 0.15 },
  "stemPatterns": ["다음 설명에 해당하는 용어를 쓰시오", "~로 옳지 않은 것은?"],
  "optionCount": 4,
  "conceptFrequency": { "전송 계층": 3, "델파이 기법": 2 }
}
```

프로파일이 꽂히는 세 지점:

1. `typeDistribution` → **유형 배분 override** (기출 없으면 기본 설정값 폴백)
2. `stemPatterns` → 생성 프롬프트의 **스타일 슬롯** (발문 말투·선지 수 모방, 내용은 참고 금지)
3. `conceptFrequency` → **예산 가중치 최상위 신호**

**원칙:** 기출 문항 자체는 은행에 절대 복사하지 않는다. 기출이 다룬 개념을 **본문 근거로, 기출 스타일로 재생성**해 그 개념이 속한 목차에 배치한다. 본문에 없는 기출 포인트는 생성 불가 → 로그 (추후 "자료에 없는 기출 내용 N개" ⚡ 안내 소재).

### ④ 예산·유형 계획 — 전부 설정값

```python
class QuizGenConfig(BaseModel):
    type_ratio = {"mcq": .4, "cloze": .25, "shortAnswer": .25, "trueFalse": .1}  # 기출 있으면 override
    per_concept_min = 1      # 커버리지 바닥: 출제 가능 개념당 최소 1문항
    per_concept_max = 3      # 중요 개념 상한
    toc_multiplier = 1.5     # 목차 예산 = clamp(개념수 × 1.5, toc_min, toc_max)
    toc_min = 15
    toc_max = 80             # 비용 천장
    overgen_ratio = 1.15     # 검증 탈락 대비 과생성
```

- **바닥 = 커버리지 보장**: 어떤 개념이 문항 0개면 그 범위는 체크해도 안 물어보는 구멍 → 개념당 최소 1.
- **추가분 = 중요도 배분**: 기출 빈도 > 다조각 등장 > 선수 그래프 참조 수.
- **천장 = 목차당 clamp**: 목차 크기 편차가 큼 (예시 파일: 목차별 개념 222~26개) → 비례식·고정값 단독으론 안 됨.
- 예산은 **호출 전에** 조각별로 쪼갠다. 만들고 버리면 비용 낭비.

### ⑤ 생성 — 조각당 LLM 1콜

- 호출 단위 = 조각(~3,500자 + 개념 십수 개). 목차 전체를 넣으면 뒤쪽 개념이 부실해짐.
- **프롬프트 = 고정 틀 + 슬롯.** 틀(출제자 역할·규칙·출력 스키마)은 코드에 고정, 슬롯(원문 / 번호 붙인 문장 목록 / 개념별 출제 지시 / 기출 스타일)은 문서·조각마다 교체. 틀이 과목 내용을 언급하지 않으므로 어떤 문서든 같은 코드로 처리.
- **근거는 문장 번호(sN)로 답하게 강제** → 코드가 번호→offset으로 결정적 변환. LLM이 offset 숫자를 직접 다루지 않게 한다. 근거 없는 문항은 즉시 폐기.
- 출력은 structured output(JSON 스키마 강제): `{type, data, evidence(sN[]), difficulty}`.
- **형태 → 유형 후보** (하나로 못박는 게 아니라 후보 집합):

| 원문 형태 | 판정 신호 | 유형 후보 |
| --- | --- | --- |
| 정의형 | "X는 ~이다" | shortAnswer(정의→용어), mcq(용어→정의), trueFalse |
| 열거형 | 리스트 3개 이상 | mcq "해당하지 **않는** 것은", multiSelect |
| 순서형 | "→" 단계 나열 | cloze(단계 빈칸) |
| 대비형 | 두 개념 vs 구조 | trueFalse, mcq(특징→개념 매칭) |

  실제 유형·개수는 예산·배분이 결정 (형태 = 메뉴판, 예산·배분 = 주문).
- mcq는 **오답 선지별 해설**(`wrongExplanations`) 필수 — "④를 고르셨네요 → ~라서 아닙니다" UX의 재료.

### ⑥ 검증 — 2중

1. **기계 검사(코드)**: 근거 번호 실존, cloze 정답이 근거 문장 안에 존재.
2. **LLM 심판(5문항 묶음)**: 정답이 근거로 뒷받침되는가 + **오답 선지 중 원문에서 참인 게 있는가**(정답 2개 방지 — 같은 조각에 유사 열거가 공존하므로 필수).
   - 불합격 → 사유 붙여 **1회만 재생성** → 재실패 폐기.
3. **기출 유사도 검사**: 실제 기출 문항과 과도하게 유사하면 폐기 (복제 방지 — 유료 기출집 저작권 방어선).
- 문항 0개로 끝난 개념은 로그 (커버리지 구멍 추적).
- `verified=true`만 저장·서빙 (README §2.5A와 같은 사상).

### ⑦ 저장

```sql
CREATE TABLE quiz_items (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  course_id   uuid NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
  document_id uuid NOT NULL REFERENCES documents(id) ON DELETE CASCADE,  -- 문서별 목차 구분
  toc_index int NOT NULL,          -- 범위 체크박스의 필터 키 (문서 내 목차 번호)
  type text NOT NULL,              -- mcq | cloze | shortAnswer | trueFalse
  concept_name text,
  data jsonb NOT NULL,             -- 봉투 data (문제·선지·정답·해설) — 프론트 registry 그대로
  evidence jsonb NOT NULL,         -- {chunkIndex, sentenceRanges[[start,end]], pageFrom, pageTo}
  difficulty smallint,
  verified boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ON quiz_items (course_id, document_id, toc_index);

CREATE TABLE quiz_attempts (       -- ★ attempts와 물리 분리 (확정안 §7-③ 데이터 격리)
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES users(id),
  quiz_item_id uuid NOT NULL REFERENCES quiz_items(id),
  correct boolean,
  user_input jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);
```

- `evidence`는 저장 직전에 문장 번호→offset 변환 (서빙 시 `raw[start:end]`로 근거 원문 슬라이스).
- 재생성 시 기존 문항 **전체 교체** (반쯤 섞인 은행 금지).
- 배치 실패 처리: 조각 단위 재시도(2~3회), 일부 조각 실패해도 나머지로 ready + 실패 기록.

### ⑧ 서빙 API — 풀 때 LLM 호출 0

| M | 경로 | 역할 |
| --- | --- | --- |
| GET | /courses/:id/quiz 🔒 | 문서별·목차별 문항 수 + 생성 상태 (진입 화면 체크박스) |
| POST | /courses/:id/quiz/session 🔒 | `{documentId?, tocIndexes[], count}` → 문항 샘플링. **정답·해설 제외** |
| POST | /quiz/attempts 🔒 | 답 제출 → 서버 채점 → `{정오, 정답, 고른 선지 해설, 근거 원문+페이지}` + 기록 |

- 정답은 서버만 보유 (클라 치팅 방지, "클라에서 검증/판단하지 않는다" 원칙).
- 은행(목차당 최대 80) ≫ 세션(10문항) → "다시 풀기"마다 다른 조합.
- 진입 화면에 확정안 고정 문구: "⚡ 이 페이지는 학습 기록을 보지 않습니다".

---

## 3. 비용 감각

정처기 실기노트 1권(목차 7, 조각 21, 개념 634) 기준:
**생성 21콜 + 검증 ~90콜 + 재생성 ~10콜 ≈ 120콜 → ~440문항, 업로드 시 1회.**
이후 모든 사용자의 모든 풀이는 DB 조회만. 비용 조절은 `toc_max`·`toc_multiplier`로 선형.

---

## 4. 미확정 — 팀원 협의 필요

1. **인터페이스 형식**: md 파일 그대로인지, md의 원본 구조화 데이터(JSON/DB)인지. → 영향 범위는 어댑터 1개뿐.
2. **기출 파싱 계약**: 문항 단위 결과에 `text / detectedType / relatedConcepts` 포함 여부. 없으면 프로파일 콜에서 우리가 분류·매칭.
3. (선택) 인사말·비내용 문장 플래그를 파서가 달아줄지 — 달아줘도 ② 필터는 유지 (방어선).

## 5. 구현 순서

1. 내부 모델 `ParsedDocument` + `QuizGenConfig` + 무결성 검증 (예시 md → 픽스처)
2. 선별·예산·유형 계획 (순수 함수 — 유닛 테스트 완전 커버)
3. 생성·검증 프롬프트 + 파이프라인 (LLM fake로 테스트)
4. `quiz_items`/`quiz_attempts` 마이그레이션 + 배치 오케스트레이션
5. 서빙 API 3개
6. 프론트 `/quiz` 페이지 (registry 재사용)
7. 기출 스타일 프로파일 (③) — 본문 파이프라인 가동 후 추가
8. 어댑터 (팀원 형식 확정 후)
