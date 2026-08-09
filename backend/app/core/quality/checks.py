"""코드 레벨 검사 — LLM을 설득하는 것보다 코드로 막는 쪽이 확실하다 (QUIZ_TUNING §5-②).

전부 (type, data, evidence_text)만 받는 순수 함수. 조각·문장번호 개념 없음.
"""
import random
import re
import zlib

from app.core.quality.grading import grade

# 내부 문장 번호(s27) 유출 검사. \b는 한글이 단어문자라 "s27에"를 못 잡음 → 룩비하인드.
# 소문자 s만: 대문자(AWS S3 등)는 정상 용어일 수 있다.
_SENTENCE_REF = re.compile(r"(?<![0-9A-Za-z])s\d+")

# 경어체 어미 검사 — 생성 규칙("시험 문체")을 심판 둘이 다 놓친 실측 사례("예측합니다").
# "아니다"도 '니다'로 끝나므로 통짜 '니다' 매칭은 금물 — 습니다/ㅂ니다 축약형만 잡는다.
# "쓰시오"류 하오체는 시험 문체라 허용.
_POLITE_ENDING = re.compile(
    r"[가-힣]*(?:습니다|[합됩입집갑옵줍봅씁납십]니다"
    r"|세요|해요|예요|까요|네요|지요|군요)(?![가-힣])"
)


def _norm(s: str) -> str:
    return re.sub(r"\s+", "", str(s))


# 내부 문장 번호 인용의 확실한 패턴만 제거 (pro3 실측 §12 — 프롬프트로 안 막힘).
# 애매한 변형은 지우지 않고 남긴다 — mechanical_check가 잡아 수정 루프로 보낸다.
_REFS = r"(?<![0-9A-Za-z])s\d+(?:\s*[,·~]\s*s?\d+)*"
_SCRUB_PATTERNS = [
    re.compile(r"[(\[（]\s*s\d+(?:\s*[,·~\-]\s*s?\d+)*\s*[)\]）]"),  # "(s31)" "[s3, s4]"
    re.compile(_REFS + r"(?:번)?(?:\s*문장)?\s*에\s*(?:따르면|의하면|따라)\s*,?\s*"),
    re.compile(_REFS + r"(?:번)?(?:\s*문장)?\s*에서(?:는)?\s*,?\s*"),
]


def scrub_sentence_refs(item_type: str, d: dict) -> None:
    """본문에 섞인 문장 번호 인용("s31에 따르면", "(s26)")을 코드로 걷어낸다.

    폐기 전에 고칠 수 있는 것을 고치는 전처리 — polish_mcq와 같은 자리(검증 직전).
    정답·accepted는 건드리지 않는다 (근거 대조·채점 계약에 걸린 필드)."""

    def clean(s):
        if not isinstance(s, str):
            return s
        out = s
        for pat in _SCRUB_PATTERNS:
            out = pat.sub("", out)
        if out == s:
            return s
        out = re.sub(r"\s{2,}", " ", out)
        out = re.sub(r"\s+(?=[.,!?])", "", out)  # 인용 제거 자리의 " ." 정리
        return out.strip()

    if item_type == "mcq":
        for key in ("question", "explanation"):
            if key in d:
                d[key] = clean(d[key])
        if isinstance(d.get("options"), list):
            d["options"] = [clean(o) for o in d["options"]]
        if isinstance(d.get("wrongExplanations"), dict):
            d["wrongExplanations"] = {k: clean(v) for k, v in d["wrongExplanations"].items()}
    elif item_type == "cloze":
        for seg in d.get("segments", []):
            if isinstance(seg, dict) and seg.get("kind") == "text":
                seg["text"] = clean(seg.get("text"))
    elif item_type == "shortAnswer":
        for key in ("prompt", "explanation"):
            if key in d:
                d[key] = clean(d[key])
    elif item_type == "trueFalse":
        for key in ("statement", "explanation"):
            if key in d:
                d[key] = clean(d[key])


def visible_texts(item_type: str, d: dict) -> list[str]:
    """학습자에게 그대로 노출되는 텍스트 필드 (문장 번호 유출 검사 대상)."""
    if item_type == "mcq":
        wrong = d.get("wrongExplanations") or {}
        opts = d.get("options") if isinstance(d.get("options"), list) else []
        return [d.get("question", ""), d.get("explanation", ""), *wrong.values(), *opts]
    if item_type == "cloze":
        return [s.get("text", "") for s in d.get("segments", []) if isinstance(s, dict)]
    if item_type == "shortAnswer":
        return [d.get("prompt", ""), d.get("explanation", "")]
    if item_type == "trueFalse":
        return [d.get("statement", ""), d.get("explanation", "")]
    return []


def polish_mcq(data: dict) -> None:
    """오답 선지 과생성 후 선별 (overgenerate-and-rank, arXiv:2405.05144 방식의 경량판).

    생성 프롬프트가 distractorPool(추가 오답 후보 {text, why})을 주면:
    기존 오답 + 후보를 합쳐 중복·정답 동치 제거 → 정답과 길이가 비슷한 순으로
    3개 선별(길이 이질성은 정답 티가 나는 고전적 단서) → 결정적 셔플로 재배치.
    풀이 없으면 아무것도 안 한다 (하위 호환).
    """
    pool = data.pop("distractorPool", None)
    options = data.get("options")
    idx = data.get("answerIndex")
    if not pool or not isinstance(options, list) or not isinstance(idx, int):
        return
    if not (0 <= idx < len(options)):
        return

    answer = str(options[idx])
    old_wrong = data.get("wrongExplanations") or {}
    # 기존 오답의 해설을 선지 문자열 기준으로 보존
    why_by_text: dict[str, str] = {}
    for i, opt in enumerate(options):
        if i != idx and str(i) in old_wrong:
            why_by_text[_norm(opt)] = old_wrong[str(i)]

    candidates: list[str] = [str(o) for i, o in enumerate(options) if i != idx]
    for entry in pool:
        if isinstance(entry, dict):
            text = str(entry.get("text", "")).strip()
            if entry.get("why"):
                why_by_text.setdefault(_norm(text), str(entry["why"]))
        else:
            text = str(entry).strip()
        if text:
            candidates.append(text)

    seen: set[str] = set()
    distractors: list[str] = []
    for c in candidates:
        n = _norm(c).lower()
        if not n or n == _norm(answer).lower() or n in seen:
            continue
        seen.add(n)
        distractors.append(c)
    if len(distractors) < 3:
        return  # 후보 부족 — 원본 유지, 판단은 mechanical_check에

    distractors.sort(key=lambda c: abs(len(c) - len(answer)))
    opts = distractors[:3] + [answer]
    # 결정적 셔플 (같은 문항 = 항상 같은 배치, 문항끼리는 다르게)
    rng = random.Random(zlib.crc32(str(data.get("question", "")).encode("utf-8")))
    rng.shuffle(opts)

    data["options"] = opts
    data["answerIndex"] = opts.index(answer)
    data["wrongExplanations"] = {
        str(i): why_by_text[_norm(o)]
        for i, o in enumerate(opts)
        if i != data["answerIndex"] and _norm(o) in why_by_text
    }


def mechanical_check(item_type: str, d: dict, evidence_text: str) -> str | None:
    """불량 사유를 반환. None = 통과."""
    evidence_norm = _norm(evidence_text)

    if item_type == "mcq":
        options = d.get("options")
        idx = d.get("answerIndex")
        if not isinstance(options, list) or len(options) != 4:
            return "mcq 선지가 4개가 아님"
        if not isinstance(idx, int) or not (0 <= idx < len(options)):
            return "mcq answerIndex 불량"
        if len(set(map(str, options))) != len(options):
            return "mcq 선지 중복"
    elif item_type == "cloze":
        segments = [s for s in d.get("segments", []) if isinstance(s, dict)]
        blanks = [s for s in segments if s.get("kind") == "blank"]
        if not blanks:
            return "cloze에 빈칸 없음"
        if len(blanks) > 2:
            return f"cloze 빈칸 {len(blanks)}개 — 2개 초과 (완전일치 채점 불가능 수준)"
        text_norm = _norm(" ".join(str(s.get("text", "")) for s in segments if s.get("kind") == "text"))
        # 빈칸이 산식의 결과 자리면 폐기 — "64 - 2 = [빈칸]"은 지문이 답을
        # 계산으로 노출한다 (실기 노트 실측: 개념 인출이 아니라 뺄셈 문제가 됨.
        # 풀이자 LLM도 계산해서 맞히므로 왕복 검증이 못 잡는다 → 코드로 차단).
        prev_text = ""
        for s in segments:
            if s.get("kind") == "blank" and _norm(prev_text).endswith(("=", "≒", "≈")):
                return "cloze 빈칸이 계산 결과 자리 (지문에 산식 노출)"
            if s.get("kind") == "text":
                prev_text = str(s.get("text", ""))
        for b in blanks:
            ans = _norm(str(b.get("answer", "")))
            # §9-② 구절 통째 빈칸 차단: 사람이 완전일치로 못 맞히는 답.
            # 풀이자 LLM은 근거 원문을 보고 복사할 수 있어 solve가 못 잡는다.
            if len(ans) > 15:
                return f"cloze 정답 '{b.get('answer')}'이 공백 제거 15자 초과 (구절 통째 빈칸)"
            if any(ch in ans for ch in "→▶"):
                return f"cloze 정답 '{b.get('answer')}'에 화살표 포함 (절차 나열 빈칸)"
            if not ans or ans not in evidence_norm:
                return f"cloze 정답 '{b.get('answer')}'이 근거 문장에 없음"
            # answer와 동일한 alias 정리 (프롬프트로 못 막는 중복 — QUIZ_TUNING §5-②)
            aliases = [a for a in b.get("aliases", []) if _norm(str(a)) != ans]
            b["aliases"] = aliases
            # 정답(또는 별칭)이 지문에 그대로 보이면 문항이 무의미 — 폐기
            for leak in [ans, *(_norm(str(a)) for a in aliases)]:
                if len(leak) >= 2 and leak in text_norm:
                    return f"cloze 정답 '{b.get('answer')}'이 지문에 노출됨"
    elif item_type == "shortAnswer":
        if not d.get("prompt") or not d.get("accepted"):
            return "shortAnswer prompt/accepted 누락"
    elif item_type == "trueFalse":
        if not d.get("statement") or not isinstance(d.get("answer"), bool):
            return "trueFalse statement/answer 불량"

    # 프롬프트로 못 막는 LLM 편차 — 생성 콜 1회가 규칙을 통째로 무시할 수 있다 (QUIZ_TUNING §7)
    for text in visible_texts(item_type, d):
        s = str(text)
        if not s:
            continue
        if m := _SENTENCE_REF.search(s):
            return f"본문에 내부 문장 번호({m.group(0)}) 노출"
        if m := _POLITE_ENDING.search(s):
            return f"본문에 경어체 어미('{m.group(0)}') — 시험 문체 위반"
    return None


def strip_answers(item_type: str, data: dict) -> dict:
    """정답·해설을 제거한 출제용 data — 서빙과 풀이자 프롬프트가 공유."""
    if item_type == "mcq":
        return {"question": data.get("question"), "options": data.get("options")}
    if item_type == "trueFalse":
        return {"statement": data.get("statement")}
    if item_type == "shortAnswer":
        return {"prompt": data.get("prompt")}
    if item_type == "cloze":
        segments = []
        for s in data.get("segments", []):
            if s.get("kind") == "blank":
                segments.append({"kind": "blank"})  # 자리만 — 정답·별칭 제거
            else:
                segments.append({"kind": "text", "text": s.get("text")})
        return {"segments": segments}
    return {}


def check_solution(item_type: str, data: dict, solver_answer) -> str | None:
    """풀이 왕복 검증 판정 (answerability round-trip).

    근거를 보고 푼 풀이자가 키 정답에 도달하지 못하면 문항이 모호하거나
    근거로 풀 수 없다는 실험적 증거다. 불량 사유 반환, None = 통과.
    """
    if solver_answer is None:
        return "풀이자 응답 없음"

    # 풀이자가 답을 1개짜리 배열로 감싸는 형식 편차(["로킹 단위"]) — 내용이 맞으면
    # 형식 때문에 죽이지 않는다. cloze는 배열이 정답 형식, mcq는 복수 원소가 신호라 제외.
    if (
        item_type in ("shortAnswer", "trueFalse")
        and isinstance(solver_answer, list)
        and len(solver_answer) == 1
    ):
        solver_answer = solver_answer[0]

    # 문자열 불리언("False") — solar-pro3 풀이자 실측 편차. 내용이 맞으면 살린다.
    if item_type == "trueFalse" and isinstance(solver_answer, str):
        low = solver_answer.strip().lower()
        if low in ("true", "false", "참", "거짓"):
            solver_answer = low in ("true", "참")

    # 빈칸 1개짜리 cloze에 배열 없이 답하는 편차 — 형식이 아니라 내용으로 판정
    if item_type == "cloze" and isinstance(solver_answer, str):
        solver_answer = [solver_answer]

    if item_type == "mcq":
        answers = solver_answer if isinstance(solver_answer, list) else [solver_answer]
        # 선지 번호 대신 선지 텍스트로 답하는 편차('REDO') — 유일하게 일치하는
        # 선지가 있으면 그 번호로 취급 (pro3 실측). 일치가 없거나 둘 이상이면 불량.
        options = data.get("options") if isinstance(data.get("options"), list) else []
        converted = []
        for a in answers:
            try:
                converted.append(int(a))
                continue
            except (TypeError, ValueError):
                pass
            if m := re.fullmatch(r"\s*(\d+)\s*번\s*", str(a)):  # "2번" 표기
                converted.append(int(m.group(1)))
                continue
            matches = [
                i for i, o in enumerate(options)
                if _norm(str(o)).lower() == _norm(str(a)).lower()
            ]
            if len(matches) != 1:
                return f"풀이자 응답 형식 불량: {solver_answer!r}"
            converted.append(matches[0])
        try:
            picked = sorted({int(a) for a in converted})
        except (TypeError, ValueError):
            return f"풀이자 응답 형식 불량: {solver_answer!r}"
        if len(picked) > 1:
            return f"풀이자가 복수 정답으로 판단: {picked} (정답 유일성 붕괴)"
        if not picked or picked[0] != data.get("answerIndex"):
            return f"풀이자가 다른 답을 고름: {picked} ≠ 정답 {data.get('answerIndex')}"
        return None

    if grade(item_type, data, solver_answer):
        return None

    # 단답 관용 — 풀이 왕복의 목적은 "풀 수 있는 문항인가"지 표기 시험이 아니다.
    # pro3 풀이자 실측 편차 3종을 내용 기준으로 재채점:
    #   '용어 : 정의 전체' → 콜론 앞 / '용어 (English)' → 괄호 제거 /
    #   '용어 방법'처럼 접미 수식 → 정답으로 시작하고 군더더기 짧으면 인정
    if item_type == "shortAnswer" and isinstance(solver_answer, str):
        trimmed = {
            solver_answer.split(":", 1)[0].strip(),
            re.sub(r"[(（][^)）]*[)）]", "", solver_answer).strip(),
        }
        for candidate in trimmed:
            if candidate and grade(item_type, data, candidate):
                return None
        a_norm = re.sub(r"\s+", "", solver_answer).lower()
        for acc in data.get("accepted", []):
            acc_norm = re.sub(r"\s+", "", str(acc)).lower()
            if acc_norm and a_norm.startswith(acc_norm) and len(a_norm) - len(acc_norm) <= 15:
                return None

    return f"풀이자 답 '{solver_answer}'이 채점 기준 불일치"
