"""API 키 없이 개발·테스트할 때 쓰는 Mock LLM.

Solar 연동 전에 seed/materials 플로우를 end-to-end로 검증한다.
"""
import json
import random

from app.core.llm.base import LLMClient

_EMBED_DIM = 4096


class MockLLMClient(LLMClient):
    async def generate(self, prompt: str, **kwargs: object) -> str:
        if "진단" in prompt or "diagnostic" in prompt.lower():
            return json.dumps(
                {
                    "questions": [
                        {
                            "concept_id": "c1",
                            "question_text": "다음 중 해당 개념의 핵심 설명으로 가장 적절한 것은?",
                            "options": ["정답 후보", "오답 A", "오답 B", "오답 C"],
                            "correct_index": 0,
                        }
                    ]
                },
                ensure_ascii=False,
            )
        if "BLOCKS_JSON" in prompt:
            # JIT 블록 생성 프롬프트(learning/generator.py)에 대응하는 유효 응답.
            # 프롬프트에 CONCEPT_NAME: <이름> 줄이 있으면 내용에 반영한다.
            name = "이 개념"
            for line in prompt.splitlines():
                if line.startswith("CONCEPT_NAME:"):
                    name = line.split(":", 1)[1].strip() or name
                    break
            return json.dumps(
                {
                    "blocks": [
                        {
                            "type": "concept",
                            "difficulty": "mid",
                            "data": {
                                "title": name,
                                "body": f"{name}의 핵심을 근거 발췌 기준으로 정리한 설명입니다.",
                                "whyItMatters": f"{name}은(는) 이후 상위 개념의 바탕이 됩니다.",
                                "example": f"예를 들어 {name}을(를) 실제 상황에 적용하면 이렇게 동작합니다.",
                                "misconception": f"{name}을(를) 비슷한 개념과 혼동하기 쉽지만, 목적이 다릅니다.",
                            },
                        },
                        {
                            "type": "table",
                            "difficulty": "mid",
                            "data": {
                                "title": f"{name} 비교",
                                "columns": ["구분", "특징", "예"],
                                "rows": [
                                    ["유형 A", "가장 기본적인 형태", "사례 1"],
                                    ["유형 B", "확장된 형태", "사례 2"],
                                ],
                                "caption": "근거 발췌의 비교 내용을 표로 정리했습니다.",
                            },
                        },
                        {
                            "type": "diagram",
                            "difficulty": "mid",
                            "data": {
                                "title": f"{name} 처리 흐름",
                                "direction": "TD",
                                "nodes": [
                                    {"id": "N1", "label": "입력"},
                                    {"id": "N2", "label": name[:38]},
                                    {"id": "N3", "label": "결과"},
                                ],
                                "edges": [
                                    {"source": "N1", "target": "N2", "label": "적용"},
                                    {"source": "N2", "target": "N3"},
                                ],
                                "caption": "근거 발췌의 절차를 도식으로 정리했습니다.",
                            },
                        },
                        {
                            "type": "analogy",
                            "difficulty": "easy",
                            "data": {"label": "비유", "text": f"{name}은(는) 정리함에 물건을 나누어 담는 것과 비슷합니다."},
                        },
                        {
                            "type": "cloze",
                            "difficulty": "mid",
                            "data": {
                                "text": f"{name}의 핵심 목적은 {{{{blank}}}} 이다.",
                                "blanks": ["중복 제거"],
                                "hint": "무엇을 없애기 위한 것일까요?",
                            },
                        },
                        {
                            "type": "mcq",
                            "difficulty": "mid",
                            "data": {
                                "question": f"{name}에 대한 설명으로 가장 적절한 것은?",
                                "options": ["근거 기반 정답", "그럴듯한 오답 A", "그럴듯한 오답 B", "무관한 오답 C"],
                                "answerIndex": 0,
                                "explanation": "근거 발췌에 직접 서술된 내용입니다.",
                            },
                        },
                        {
                            "type": "explainBack",
                            "difficulty": "hard",
                            "data": {
                                "prompt": f"{name}이(가) 왜 필요한지 자신의 말로 설명해 보세요.",
                                "rubric": ["핵심 목적", "적용 상황"],
                            },
                        },
                    ]
                },
                ensure_ascii=False,
            )
        return f"[mock] {prompt[:120]}"

    async def embed(self, text: str) -> list[float]:
        # 결정적 pseudo-embedding (pgvector 저장 테스트용)
        seed = sum(ord(c) for c in text[:200])
        rng = random.Random(seed)
        return [rng.uniform(-0.1, 0.1) for _ in range(_EMBED_DIM)]


mock_client = MockLLMClient()
