# 문제 생성 — 파싱 결과 JSON 입력 계약

> 파서 담당자용. 파싱 결과를 이 JSON 형식으로 넘겨주면 문제 생성 파이프라인이 그대로 받는다.
> 전달 방법: `POST /api/courses/{course_id}/quiz/generate` 의 요청 바디, 또는 이 모양의 JSON 파일.

---

## 1. 전체 구조

```jsonc
{
  "document_id": "문서 UUID",
  "parsed": {
    "parser_version": "3.0",        // 문자열. 어떤 값이든 허용 (기록용)
    "source_name": "pilgi.pdf",     // 선택. 원본 파일명
    "tocs": [ ... ],                // 목차 목록
    "chunks": [ ... ]               // 조각 목록
  }
}
```

## 2. tocs — 목차

```jsonc
{
  "index": 0,                       // 목차 번호 (0부터). 문항의 소속·범위 필터 키가 됨
  "title": "1. 소프트웨어 설계",
  "chunk_indexes": [0, 1, 2]        // 이 목차에 속한 조각 번호들
}
```

규칙:
- `chunk_indexes`가 가리키는 조각은 `chunks`에 실제로 존재해야 함
- 한 조각이 두 목차에 중복 배정되면 안 됨

## 3. chunks — 조각

```jsonc
{
  "index": 0,
  "page_from": 1,                   // 원본 PDF 페이지 (근거 표시 "교재 N쪽"에 사용)
  "page_to": 4,
  "raw_text": "원문 그대로...",      // ★ 무가공. 요약·정제·트림 금지
  "sentences": [                    // 문장 앵커 — raw_text 기준 문자 offset
    { "start": 0, "end": 20 },      // raw_text[start:end] = 문장 (파이썬 슬라이스 기준, end 미포함)
    { "start": 20, "end": 49 }
  ],
  "concepts": [
    {
      "name": "폭포수 모형",
      "definition": "이전 단계로 돌아갈 수 없는 고전적 생명 주기 모형",
      "prereqs": ["소프트웨어 생명 주기"]   // 선수 개념 이름들. 없으면 [] 또는 생략
    }
  ],
  "figures": [                      // 그림. 없으면 [] 또는 생략
    {
      "page": 1,
      "offset": 973,                // raw_text 내 위치 (문자 offset)
      "kind": "figure",             // "figure" | "chart"
      "needs_vision": true          // true = 그림을 봐야 이해됨 → 주변 문장 출제 제외
    }
  ]
}
```

규칙 (수신 시 자동 검증됨 — 어기면 에러 리포트 반환):
- 모든 앵커는 `0 <= start < end <= len(raw_text)`
- 앵커끼리 겹치지 않게, 순서대로
- **offset은 글자(문자) 단위** — 바이트 단위 아님 (한글 1글자 = 1)
- `raw_text`는 md 리포트의 ```text 펜스 안 내용과 동일해야 함 (개행·공백 포함)

## 4. 기출 문서 (선택 — 형식 협의 중)

기출은 위 형식이 아니라 **문항 단위**로:

```jsonc
{
  "kind": "exam",
  "questions": [
    {
      "text": "다음 설명에 해당하는 용어를 쓰시오: ...",
      "detected_type": "shortAnswer",        // 가능하면. 없으면 우리가 분류
      "related_concepts": ["델파이 기법"]     // 가능하면. 없으면 우리가 매칭
    }
  ]
}
```

## 5. 최소 예시 (그대로 보내면 동작하는 완전한 예)

```json
{
  "document_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "parsed": {
    "parser_version": "3.0",
    "tocs": [
      { "index": 0, "title": "1. 소프트웨어 설계", "chunk_indexes": [0] }
    ],
    "chunks": [
      {
        "index": 0,
        "page_from": 1,
        "page_to": 1,
        "raw_text": "폭포수 모형은 이전 단계로 돌아갈 수 없는 고전적 생명 주기 모형이다. 나선형 모형은 계획 수립 → 위험 분석 → 개발 및 검증 → 고객 평가를 반복한다.",
        "sentences": [
          { "start": 0, "end": 40 },
          { "start": 41, "end": 85 }
        ],
        "concepts": [
          { "name": "폭포수 모형", "definition": "고전적 생명 주기 모형", "prereqs": [] },
          { "name": "나선형 모형", "definition": "위험 분석을 반복하는 점진적 모형", "prereqs": [] }
        ],
        "figures": []
      }
    ]
  }
}
```

## 6. 참고

- 실제 파싱 md에서 추출한 큰 예시: `backend/tests/fixtures/parsed_sample.json` (`parsed` 부분의 모양과 동일)
- 수신 검증 규칙 상세: `backend/app/features/quiz/intake.py`
- JSON Schema가 필요하면: `ParsedDocument.model_json_schema()` (backend/app/features/quiz/schemas.py)
