"""오프라인 sLLM(EXAONE-4.0-1.2B, 로컬 llama-server) 호출 래퍼 — stdlib 전용.

MVP(feat/ondevice-exaone-mvp) llm.py의 오프라인 절반을 이식. 함정 노하우:
  - EXAONE 4.0은 thinking 모드가 기본 — no_think 안 하면 reasoning이 토큰을
    다 먹고 finish_reason=length로 답이 비어 나온다.
  - 작은 모델이라 프롬프트에 예시(few-shot)를 넣으면 그대로 베낀다 — 예시 금지.
  - json 파싱은 첫 '{'~마지막 '}' 방어 슬라이스.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request

LOCAL_URL = "http://127.0.0.1:8080/v1/chat/completions"


def llama_alive(timeout: float = 1.5) -> bool:
    try:
        req = urllib.request.Request("http://127.0.0.1:8080/health")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status == 200
    except Exception:  # noqa: BLE001
        return False


def chat(
    prompt: str,
    *,
    json_mode: bool = False,
    max_tokens: int = 512,
    temperature: float = 0.2,
    timeout: int = 60,
) -> str:
    payload: dict = {
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens,
        # EXAONE 4.0 thinking 모드 off — reasoning 토큰 소진 방지(필수)
        "chat_template_kwargs": {"enable_thinking": False},
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    req = urllib.request.Request(
        LOCAL_URL,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = json.loads(r.read().decode())
    return body["choices"][0]["message"]["content"] or ""


def chat_json(prompt: str, **kw) -> dict | None:
    """JSON 응답 강제 + 방어 파싱. 실패 시 None(호출측 폴백)."""
    try:
        raw = chat(prompt, json_mode=True, **kw)
        start, end = raw.find("{"), raw.rfind("}")
        if start == -1 or end == -1:
            return None
        return json.loads(raw[start : end + 1])
    except Exception:  # noqa: BLE001
        return None
