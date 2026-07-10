> ✅ **결착(2026-07-10)** — parsing 팀원이 `feat/yoonhs-integration`(UUID 정본 계보)을 베이스로 채택하며 ISSUE-001 해소. 잔여는 마이그레이션 스쿼시(0001~0020 → 단일 0001, **동시 진행**)뿐. 이하는 협의 당시의 역사 기록.

# parsing ↔ backend-ai-core 병합 합의 요청 (ISSUE-001 · ISSUE-015)

> 보내는 쪽: `feat/backend-ai-core`(하류, yoonhs) → 받는 쪽: `feat/parsing` 담당
> 목적: 시드 픽스처가 아닌 **실데이터로 end-to-end(업로드→진단→학습)**를 완결하려면 두 가지 합의가 필요합니다.
> 근거 정본: `dev/docs/SCHEMA.md`(UUID 스키마) · `docs/GRAPH_ORIENTATION_CONTRACT.md`(그래프 방향, 이미 parsing 규약 채택)

---

## ISSUE-001 — PK 타입 + 마이그레이션 통일 (🔴 병합 블로커)

**문제**: 두 브랜치가 `0002`부터 마이그레이션 계보가 완전히 갈렸고, PK 타입이 다릅니다.
- backend-ai-core: **UUID** PK (전 테이블 `gen_random_uuid()`)
- parsing: **Integer** PK

같은 DB에서 두 스키마가 공존 불가 → 병합 시 alembic 충돌 + FK 타입 불일치.

**제안 (정본=UUID 기준)**
1. **PK를 UUID로 통일.** 근거: `dev/docs/SCHEMA.md`가 전 테이블 `uuid PRIMARY KEY DEFAULT gen_random_uuid()`. → parsing이 Integer→UUID로 이관.
   - (참고: parsing seed가 이미 "concept_mastery는 UUID 이관 시점에"로 미뤄둔 그 지점입니다.)
2. **마이그레이션 스쿼시.** 통합 시점에 양쪽 `alembic/versions/*` 전부 삭제 → 정본(UUID) 통합 모델로 **단일 `0001_initial`** 재작성. prod 데이터 없어 히스토리 버려도 무손실. ⚠️ **둘이 동시에** 진행(단독 금지).
3. **모듈 배치 합의.** parsing은 `documents/` 한 파일에 chapters/sections/concepts/doc_chunks, 우리는 `curriculum/`+`seed/`+`materials/`로 분리. 통합 배치를 정본 SCHEMA.md 구조 기준으로 하나로.

**parsing 측 필드 정합 목록 (정본에 맞춤)**
| 대상 | parsing 현재 | 정본(맞출 것) |
|---|---|---|
| `enrollments` | `floor_concept_id`/`ceiling_concept_id` | `floor_concept`/`ceiling_concept` + `diag_status`·`diag_q_count` 추가 |
| `concepts.key` | nullable | NOT NULL + UNIQUE(course_id, key) |
| `concepts.source` | default `'document'` | `book` \| `ai_prereq` |

**그래프 방향**: `concept_edges`(from=의존→to=선수) / depth(선수일수록 큼) / 진행축=커리큘럼 순서 — **이미 parsing 규약을 우리가 채택**(ISSUE-012). 병합 시 parsing이 실제 그 규약대로 생산하는지만 대조.

---

## ISSUE-015 — RAG 임베딩 모델 (🟢 정확성, 작은 변경)

**목표**: 개념→청크 근거 검색 정확도 최적화(교육 플랫폼 = 정확성 우선).

**제안 — 비대칭 임베딩 (Solar query/passage 쌍)**
| 대상 | 모델 | 상태 |
|---|---|---|
| 개념(concept) | `embedding-query` | parsing 이미 이렇게 함 ✅ |
| 청크(doc_chunk) | `embedding-passage` | parsing 현재 `embedding-query` → **`SOLAR_EMBED_MODEL`을 passage로 변경(1줄)** |

- 이유: 개념(짧은 질의) ↔ 청크(긴 문단)는 비대칭 검색. Solar query/passage는 정확히 이 쌍을 위해 훈련됨 → 대칭(둘 다 query)보다 정확. 둘 다 4096차원.
- **우리 downstream은 parsing이 저장한 `concepts.embedding`을 소비**(재임베딩 안 함) → 병합 시 우리 Concept 모델에 `embedding` 컬럼 추가.
- 검색 로직(`search_concept_chunks`, pgvector cosine)은 우리 쪽에 이미 구현·검증됨.

---

## parsing이 우리에게 넘겨줘야 하는 것 (인수인계 계약, 확인용)
서빙이 시작되려면 아래가 채워져 있으면 됩니다:
- `courses` · `chapters` · `sections`(concept_id, order_index) · `concepts`(key, depth_level, source, **embedding**)
- `concept_edges`(prerequisite, 방향 규약대로)
- `enrollments.floor_concept`/`ceiling_concept`(진단 산출)
- `doc_chunks`(content, **embedding=passage**)

## 요청 정리
1. **ISSUE-001**: PK UUID 통일 + 마이그 스쿼시 시점을 **함께** 잡기(동시 진행). 필드 정합 3건 반영.
2. **ISSUE-015**: 청크 임베딩 모델을 `embedding-passage`로 변경(1줄).
3. 위 인수인계 계약 필드가 parsing 산출물에 다 있는지 확인.
