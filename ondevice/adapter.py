"""로컬 엔진 어댑터(:8600) — 클라우드+로컬 이중구조의 로컬 절반 (제안서 차별점 ④).

역할: 평소(온라인)엔 아무것도 안 함. 브라우저가 절을 열 때 /sync로 오프라인
팩(정답 포함)을 백엔드에서 미리 당겨 두고, 인터넷/서버가 끊기면 브라우저의
채점 요청(POST /api/attempts — 본 서비스와 동일 계약)을 로컬 sLLM
(EXAONE-4.0-1.2B, llama-server :8080)으로 이어받는다.

채점 경계(온디바이스 결정문): 생성=온라인 전용, 채점·판정=오프라인 가능.
  - mcq        : answerIndex 비교(LLM 불필요)
  - cloze      : 정규화 동등/포함 → 불일치만 1.2B 인정판정(표기차 FN 완화)
  - explainBack: 1.2B 루브릭 커버리지 채점(놓친 포인트 + 코멘트)

stdlib 전용(의존성 0) — 사용자 기기에서 파이썬만으로 돈다. 실행: run_local.sh.
보안 노트: 팩에는 정답이 있다. 어댑터는 사용자 본인 기기의 신뢰 컴포넌트라는
전제(데모 범위)이며, 브라우저 학습 UI에는 정답이 가지 않는다.
"""
from __future__ import annotations

import json
import os
import re
import unicodedata
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import local_llm

PORT = 8600
CACHE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache", "packs.json")
DEV_USER = "00000000-0000-0000-0000-000000000001"

# blockId → {"type", "data", "sectionTitle", "conceptName"}
_PACKS: dict[str, dict] = {}
_SECTIONS: set[str] = set()


def _load_cache() -> None:
    global _PACKS, _SECTIONS
    try:
        with open(CACHE_PATH, encoding="utf-8") as f:
            saved = json.load(f)
        _PACKS = saved.get("blocks", {})
        _SECTIONS = set(saved.get("sections", []))
    except Exception:  # noqa: BLE001 — 캐시 없으면 빈 상태
        pass


def _save_cache() -> None:
    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump({"blocks": _PACKS, "sections": sorted(_SECTIONS)}, f, ensure_ascii=False)


# ── 채점 (백엔드 grading과 같은 철학의 축소판) ────────────────────────────────
def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", str(s)).lower().strip()
    return re.sub(r"[\s\.\,\'\"\(\)\[\]·]+", "", s)


def _answers_match(expected: str, got: str) -> bool:
    e, g = _norm(expected), _norm(got)
    return bool(e) and bool(g) and (e == g or e in g or g in e)


def _grade_prompt(question: str, reference: str, user_answer: str) -> str:
    # MVP prompts.grade_prompt 이식 — 표현 차이 관대, 개념 오류 엄격, 예시 금지.
    return f"""아래 학생의 답을 채점하세요.
학생 답이 기준 정답과 같은 뜻이면 correct=true, 다른 개념이거나 빈 답/모른다는 답이면 correct=false.
맞춤법·표현·어순 차이는 무시하고 의미로만 판단하세요.

문제: {question}
기준 정답: {reference}
학생 답: {user_answer}

reason에는 이 문제의 기준 정답과 학생 답을 직접 비교해 쓰세요.
JSON으로만 답하세요:
{{"reason": "<기준 정답과 학생 답 비교>", "correct": <true/false>}}"""


def _grade_cloze(data: dict, user_input) -> dict:
    blanks = [str(b) for b in (data.get("blanks") or [])]
    answers = [str(a) for a in (user_input or [])] if isinstance(user_input, list) else [str(user_input)]
    results: list[bool] = []
    for i, expected in enumerate(blanks):
        got = answers[i] if i < len(answers) else ""
        ok = _answers_match(expected, got)
        if not ok and got.strip():
            # 표기차 FN 완화 — 로컬 1.2B 인정판정(불일치 빈칸만, 콜 최소화).
            # CPU 지연 억제: 문제문 300자 컷 + max_tokens 축소.
            verdict = local_llm.chat_json(
                _grade_prompt(str(data.get("text", ""))[:300], expected, got[:200]),
                max_tokens=120,
            )
            ok = bool(verdict and str(verdict.get("correct")).lower() == "true")
        results.append(ok)
    correct = bool(results) and all(results)
    return {
        "correct": correct,
        "score": None,
        "feedback": None,
        "reveal": {
            "blanks": blanks,
            "blankResults": results,
            "explanation": data.get("hint") or None,
        },
    }


def _grade_mcq(data: dict, user_input) -> dict:
    try:
        picked = int(user_input)
    except (TypeError, ValueError):
        picked = -1
    answer = data.get("answerIndex")
    correct = isinstance(answer, int) and picked == answer
    return {
        "correct": correct,
        "score": None,
        "feedback": None,
        "reveal": {"answerIndex": answer, "explanation": data.get("explanation")},
    }


def _explain_batch_prompt(question: str, rubric: list[str], answer: str) -> str:
    points = "\n".join(f"{i + 1}. {p[:150]}" for i, p in enumerate(rubric))
    return f"""학생의 서술형 답안을 채점 기준 항목별로 평가하세요.
각 항목의 내용이 학생 답에 (표현이 달라도) 의미상 들어 있으면 true, 없거나 틀리면 false.

문제: {question[:200]}
채점 기준:
{points}
학생 답: {answer[:600]}

JSON으로만 답하세요(covered는 기준 항목 순서대로 {len(rubric)}개):
{{"covered": [true/false, ...]}}"""


def _grade_explain(data: dict, user_input, *, concept: str) -> dict:
    rubric = [str(r) for r in (data.get("rubric") or [])]
    answer = str(user_input or "").strip()
    if not answer:
        return {"correct": False, "score": 0.0,
                "feedback": {"missedPoints": rubric, "comment": "답이 비어 있어요. 위 설명을 보고 자신의 말로 적어보세요."},
                "reveal": None}
    # 루브릭 전체를 배치 1콜로(CPU 지연: 항목당 1콜이면 수십 초 실측 → 1콜 ~10초)
    covered: list[bool] = []
    verdict = local_llm.chat_json(
        _explain_batch_prompt(data.get("prompt", ""), rubric, answer), max_tokens=120
    )
    got = verdict.get("covered") if isinstance(verdict, dict) else None
    if isinstance(got, list) and len(got) == len(rubric):
        covered = [str(v).lower() == "true" for v in got]
    else:
        # 배치 파싱 실패 폴백 — 항목별 개별 판정(느리지만 정확)
        for point in rubric:
            v = local_llm.chat_json(
                _grade_prompt(str(data.get("prompt", ""))[:200], point[:150], answer[:400]),
                max_tokens=120,
            )
            covered.append(bool(v and str(v.get("correct")).lower() == "true"))
    score = (sum(covered) / len(covered)) if covered else 0.0
    missed = [p for p, ok in zip(rubric, covered) if not ok]
    comment = (
        "핵심을 잘 짚었어요!" if score >= 0.6
        else f"'{concept}'의 핵심 포인트를 다시 확인해보세요."
    )
    return {"correct": score >= 0.6, "score": round(score, 2),
            "feedback": {"missedPoints": missed, "comment": comment}, "reveal": None}


def grade(block: dict, user_input) -> dict:
    btype = block.get("type")
    data = block.get("data") or {}
    if btype == "mcq":
        out = _grade_mcq(data, user_input)
    elif btype == "cloze":
        out = _grade_cloze(data, user_input)
    elif btype in ("explainBack", "reviewGate"):
        out = _grade_explain(data, user_input, concept=block.get("conceptName") or "")
    else:
        out = {"correct": None, "score": None, "feedback": None, "reveal": None}
    out["offline"] = True  # 프론트가 "오프라인 채점" 배지를 띄우는 표식
    return out


# ── 팩 동기화 ────────────────────────────────────────────────────────────────
def sync_sections(backend_url: str, section_ids: list[str], user_id: str) -> int:
    added = 0
    for sid in section_ids:
        req = urllib.request.Request(
            f"{backend_url}/api/sections/{sid}/offline-pack",
            headers={"X-User-Id": user_id or DEV_USER},
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            pack = json.loads(r.read().decode())
        for b in pack.get("blocks", []):
            _PACKS[b["id"]] = {
                "type": b.get("type"),
                "data": b.get("data") or {},
                "conceptName": pack.get("conceptName"),
                "sectionTitle": pack.get("title"),
            }
            added += 1
        _SECTIONS.add(sid)
    _save_cache()
    return added


# ── HTTP 서버 (CORS 포함 — 브라우저 55173에서 직접 호출) ─────────────────────
class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-User-Id")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:  # noqa: N802 — CORS preflight
        self._send(204, {})

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            self._send(200, {
                "ok": True,
                "llama": local_llm.llama_alive(),
                "sections": len(_SECTIONS),
                "blocks": len(_PACKS),
            })
        else:
            self._send(404, {"detail": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(length).decode() or "{}")
        except json.JSONDecodeError:
            self._send(400, {"detail": "invalid json"})
            return
        if self.path == "/sync":
            try:
                n = sync_sections(
                    body.get("backendUrl") or "http://localhost:48001",
                    list(body.get("sectionIds") or []),
                    body.get("userId") or DEV_USER,
                )
                self._send(200, {"synced": n, "sections": len(_SECTIONS)})
            except Exception as exc:  # noqa: BLE001
                self._send(502, {"detail": f"sync failed: {exc}"})
        elif self.path == "/api/attempts":
            block = _PACKS.get(str(body.get("blockId")))
            if block is None:
                self._send(404, {"detail": "block not in offline pack — 온라인일 때 이 절을 열어 동기화하세요"})
                return
            self._send(200, grade(block, body.get("userInput")))
        else:
            self._send(404, {"detail": "not found"})

    def log_message(self, fmt: str, *args) -> None:  # 콘솔 소음 축소
        print(f"[adapter] {self.address_string()} {fmt % args}")


def _warmup() -> None:
    """기동 직후 1토큰 워밍업 — 첫 실채점의 콜드스타트(프롬프트 캐시·페이지인) 제거."""
    try:
        local_llm.chat("안녕", max_tokens=8, timeout=120)
        print("[adapter] llama 워밍업 완료")
    except Exception as exc:  # noqa: BLE001
        print(f"[adapter] 워밍업 실패(무시): {exc}")


if __name__ == "__main__":
    import threading

    _load_cache()
    print(f"[adapter] :{PORT} 기동 — packs {len(_PACKS)}블록/{len(_SECTIONS)}절, llama={'ok' if local_llm.llama_alive() else 'DOWN'}")
    threading.Thread(target=_warmup, daemon=True).start()
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
