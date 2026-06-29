# MetaLearn — UI 컴포넌트 작업 브리프

## 우리가 만드는 것 (한 문단)

MetaLearn은 사용자가 올린 학습 자료(PDF 등)를 AI가 분석해 **1:1 맞춤 커리큘럼**을 짜고, **능동형 인출 학습**을 시키는 AI 튜터입니다. ChatGPT처럼 답을 떠먹이지 않고, **AI가 먼저 빈칸·역질문을 던지고 사용자가 답해야 다음으로 넘어가는** 구조가 핵심. 사실(콘텐츠)은 원본 자료에 묶고, 개인화(약점·난이도·복습)는 그 위에 얹습니다.

## 컴포넌트의 3가지 종류

모든 학습 블록은 아래 셋 중 하나입니다.

| 종류 | 한마디로 | 사용자 행동 | 추적 |
|------|----------|-------------|:---:|
| **① 설명** | 보여준다 | 읽는다 | ❌ |
| **② 문제** | 꺼내게 한다 | 답한다 | ✅ |
| **③ 인터랙티브** | 조작하게 한다 | 만지작거린다 | ✅ |

학습 루프: **①로 보여주고 → ②로 직접 꺼내게 하고 → ③으로 체득 → (복습으로 반복).**

## UI가 지켜야 할 4대 원칙

1. **컴포넌트 고정 + 데이터 주입** — UI 컴포넌트는 미리 만들어 두고, AI는 JSON 데이터만 채움. 컴포넌트가 HTML을 생성하지 않음.
2. **공통 래퍼 통일** — 모든 블록은 동일한 래퍼. `type`으로 컴포넌트를 고르고 `data`만 넘김.
3. **답해야 진행 (회피 불가)** — ②③ 블록은 `idle → answered → correct/incorrect → revealed` 상태머신 내장. 답하기 전엔 다음으로 못 감.
4. **추적 콜백 공유** — ②③ 블록이 같은 콜백으로 결과를 위로 올림 → 개념별 숙련도 추적. (①은 콜백 없음.)

## 공통 기반 기능 (수식 렌더링)
- **KaTeX / LaTeX 렌더링 기본 장착**: `concept`, `mcq`, `cloze` 등 텍스트가 출력되는 모든 블록은 공통적으로 수식을 렌더링할 수 있어야 합니다. (새로운 type이 아니라, 기존 블록 내부의 텍스트 파서 역할)
- **이유**: 수학/물리/화학 등의 이과 과목은 텍스트가 곧 수식입니다. 기반 기능으로 한 번 장착하면 41개 모든 컴포넌트에서 수식을 지원할 수 있어 효율적입니다.

## 공통 데이터 구조

```json
{
  "id": "blk_017",
  "type": "cloze",
  "conceptId": "photosynthesis_basic",
  "source": "book",            // book | ai  (📖 / 🤖 출처 표시)
  "data": { /* type별 필드 */ },
  "meta": { "difficulty": "mid", "version": 1 }
}
```

## 공통 콜백 시그니처

```js
// 정답이 있는 블록 (②문제, ③정답형 인터랙티브)
onAnswer({ blockId, conceptId, correct, userInput })
// 정답 없는 탐색형 (③슬라이더 등)
onInteract({ blockId, conceptId, action })
```

> 우선순위 표기: 🔴 필수(없으면 학습 루프가 안 돎) · 🟡 권장(제품다워짐) · ⚪ 나중에(같은 래퍼에 type만 추가)

---

## 컴포넌트 카탈로그

### ① 설명 컴포넌트 — 보여준다 / 읽는다 / 추적 ❌

| type | 용도 | data 핵심 필드 | 우선순위 | 구현 |
|------|------|----------------|:---:|:---:|
| `concept` | 개념 설명 본문 | `title`, `body`, `source` | 🔴 필수 | [O] |
| `callout` | 강조/주의/팁 | `variant`(info·warn·tip), `text` | 🟡 권장 | [O] |
| `definition` | 용어 정의 카드 | `term`, `meaning`, `example` | 🟡 권장 | [O] |
| `image` | 이미지 | `src`, `caption`, `alt` | 🟡 권장 | [O] |
| `chart` | 그래프(막대·선·원·산점도) | `chartType`, `series[]`, `xLabel`, `yLabel` | 🟡 권장 | [O] |
| `analogy` | 비유·발판 (사실 아님 라벨) | `text`, `label:"비유"` | ⚪ 나중에 | [O] |
| `keyTakeaways` | 핵심 요약 리스트 | `items[]` | ⚪ 나중에 | [O] |
| `code` | 코드 예시 (보여주기 전용. 실행은 codeExercise) | `lang`, `content` | ⚪ 나중에* | [O] |
| `timeline` | 연표·단계 | `events[]`(date·title·desc) | ⚪ 나중에 | [O] |
| `tree` | 위계·분류도 | `nodes[]`, `edges[]` | ⚪ 나중에 | [O] |
| `flow` | 순서도·프로세스 | `nodes[]`, `edges[]`, `direction` | ⚪ 나중에 | [O] |
| `table` | 비교표 | `headers[]`, `rows[][]` | ⚪ 나중에 | [O] |
| `conceptMap` | 개념 연결망(숲) | `nodes[]`, `links[]` | ⚪ 나중에 | [O] |

\* 코딩 과목이면 `code`는 🟡로 올라감. 정형 시각화(chart~conceptMap)는 표현만 다를 뿐 전부 "보여주기"라 ① 식구.

### ② 문제 컴포넌트 — 꺼내게 한다 / 답한다 / 추적 ✅ (제품의 심장)

| type | 용도 | data 핵심 필드 | 우선순위 | 구현 |
|------|------|----------------|:---:|:---:|
| `cloze` | 본문 속 빈칸 (코딩 '빈칸 코드 채우기'로 확장 가능) | `segments[]`(text/blank), `answers[]`, `aliases[]` | 🔴 필수 | [O] |
| `mcq` | 객관식 (코드 출력 예측 등에 활용 가능) | `question`, `options[]`, `answerIndex`, `explanation` | 🔴 필수 | [O] |
| `explainBack` | 파인만식 역질문("설명해봐") | `prompt`, `rubric[]` | 🔴 필수 | [O] |
| `codeExercise`| 직접 코드 작성 및 실행 (코딩 필수 인출) | `language`, `initialCode`, `testCases[]` | 🔴 타겟따라 | [O] |
| `mathInput` | 수식 및 풀이 단계 직접 입력 (수학 필수 인출) | `prompt`, `correctExpression`, `variables[]` | 🔴 타겟따라 | [ ] |
| `shortAnswer` | 단답 | `prompt`, `accepted[]`, `caseSensitive` | 🟡 권장 | [O] |
| `trueFalse` | O/X | `statement`, `answer`, `explanation` | ⚪ 나중에 | [O] |
| `multiSelect` | 복수정답 | `options[]`, `answerIndexes[]` | ⚪ 나중에 | [ ] |
| `ordering` | 순서 맞추기 | `items[]`, `correctOrder[]` | ⚪ 나중에 | [ ] |
| `matching` | 짝 연결 | `left[]`, `right[]`, `pairs[]` | ⚪ 나중에 | [ ] |
| `categorize` | 분류(드래그) | `buckets[]`, `items[]`, `mapping` | ⚪ 나중에 | [ ] |

### ③ 인터랙티브 컴포넌트 — 조작하게 한다 / 만지작거린다 / 추적 ✅

| type | 용도 | LLM이 채우는 파라미터 | 우선순위 | 구현 |
|------|------|----------------------|:---:|:---:|
| `stepReveal` | 풀이 단계별 한 줄씩 공개 | `steps[]`(content·optional blank) | 🟡 권장 | [O] |
| `sliderExplore` | 변수 조절 → 결과 변화 | `formula`, `variables[]`(min·max·step), `outputType` | ⚪ 나중에 | [O] |
| `labeledDiagram` | 도식에 라벨 드래그 | `image`/`shape`, `labels[]`, `dropZones[]` | ⚪ 나중에 | [ ] |
| `sortableSteps` | 절차·알고리즘 재배열 | `steps[]`, `correctOrder[]` | ⚪ 나중에 | [ ] |
| `numberLine` | 수직선 위 값 이동 | `min`, `max`, `markers[]`, `target` | ⚪ 나중에 | [ ] |
| `hotspot` | 그림 특정 부위 클릭/식별 | `image`, `regions[]`(coords·answer) | ⚪ 나중에 | [ ] |
| `parametricChart` | 슬라이더로 그래프 변형 | `function`, `params[]`, `range` | ⚪ 나중에 | [ ] |
| `comparisonSlider` | Before/After 비교 | `leftContent`, `rightContent` | ⚪ 나중에 | [O] |
| `tabbedExplain` | 관점별 탭 | `tabs[]`(label·body·source) | ⚪ 나중에 | [O] |
| `interactiveTable` | 행/열 채우기형 표 | `headers[]`, `blanks[]`, `answers[]` | ⚪ 나중에 | [ ] |
| `formulaBuilder` | 조각으로 공식·문장 조립 | `pieces[]`, `correctExpression` | ⚪ 나중에 | [ ] |
| `matrixGrid` | 격자 채우기(구구단·진리표) | `rows[]`, `cols[]`, `answerGrid[][]` | ⚪ 나중에 | [ ] |

### 흐름 제어 (컴포넌트라기보단 학습 흐름 장치)

| type | 용도 | data 핵심 필드 | 우선순위 | 구현 |
|------|------|----------------|:---:|:---:|
| `reviewGate` | 망각곡선 복습 팝업 | `concepts[]`, `dueItems[]` | 🔴 필수 | [O] |
| `sectionHeader` | 절·개념 제목 + 진행률 | `title`, `conceptId`, `progress` | 🟡 권장 | [O] |
| `confidenceCheck` | 스킵 3단계 빠른 체크 | `conceptId`, `quickItems[]` | ⚪ 나중에 | [O] |
| `connection` | 옛+새 개념 연결 퀴즈 | `oldConceptId`, `newConceptId`, `question` | ⚪ 나중에 | [ ] |
| `hintLadder` | 단계별 힌트 (선제 개입) | `hints[]`(점진 공개) | ⚪ 나중에 | [ ] |

---

## 빌드 우선순위

> **💡 타겟 과목별 1차 필수 우선순위 분기**
> 1차 필수 5개(`concept`, `cloze`, `mcq`, `explainBack`, `reviewGate`)는 기본적으로 어학·인문 기준입니다. 타겟 과목에 따라 우선순위가 바뀝니다.
> - **코딩 메인**: 1차 필수 목록에 **`codeExercise`**가 반드시 포함되어야 합니다.
> - **수학 메인**: 1차 필수 목록에 **`mathInput`**과 **공통 수식 렌더(KaTeX)**가 반드시 포함되어야 합니다.

**1차 (학습 루프 최소 = 래퍼 + 5개):** 공통 래퍼 + `onAnswer` 콜백 → `concept` · `cloze` · `mcq` · `explainBack` · `reviewGate`
이 5개면 **보여주고 → 꺼내고 → 설명시키고 → 복습**이 다 돕니다. MetaLearn이 ChatGPT와 다른 최소 단위.

**2차 (제품다워지는 단계):** `callout` · `definition` · `image` · `chart` · `shortAnswer` · `stepReveal` · `sectionHeader`

**3차 (확장):** 나머지 전부 — ③인터랙티브 통째로, 다양한 문제 유형, 정형 시각화 확장. 전부 같은 래퍼에 `type`만 추가.

## 컴포넌트마다 구현 시 챙길 것

- ②③ 블록은 **상태머신 내장** + 정답 전 진행 차단
- ②③ 블록은 **동일 콜백 시그니처**로 결과 방출 (①은 콜백 없음)
- **미지원 type 폴백** 컴포넌트(에러 대신 "표시 불가 + 재생성" 카드)
- props 타입 = **zod/TS 스키마**로 정의 (AI 출력 스키마와 1:1로 묶임)

---

## 안티그래비티에 시킬 때 (예시 프롬프트)

> 이 브리프의 **1차 5개**부터 만들어줘. 공통 래퍼(`{id, type, conceptId, source, data, meta}`)와 `onAnswer({blockId, conceptId, correct, userInput})` 콜백 구조를 먼저 잡고, `concept`·`cloze`·`mcq`·`explainBack`·`reviewGate`를 React 컴포넌트로. type별 props는 카탈로그의 data 필드대로, zod 스키마로 정의해줘. type→컴포넌트 레지스트리 하나로 묶고, 미지원 type은 폴백 카드로. 나머지 type은 나중에 같은 래퍼에 추가할 거야.
