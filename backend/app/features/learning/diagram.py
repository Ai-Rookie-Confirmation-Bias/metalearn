"""[3.Service] diagram 블록 — Mermaid 결정적 조립 + faithfulness 문장화.

상위 설계: LLM에게 Mermaid 문법을 직접 쓰게 하지 않는다. LLM은 그래프
JSON(nodes/edges)만 만들고(schemas.DiagramData가 정합성 게이트), 여기서
코드가 Mermaid 문자열을 조립한다 → 문법 오류가 구조적으로 불가능하고,
click·%%{init}%% 같은 위험 지시어는 조립기가 안 만들므로 존재 자체가 불가능
(인젝션 방어가 공짜). 순수 계층: LLM/DB 비의존.
"""
from __future__ import annotations


def _escape(s: str) -> str:
    """Mermaid 라벨 이스케이프 — 문법을 깨는 문자를 안전한 대체로."""
    return (
        s.replace('"', "'")
        .replace("`", "'")
        .replace("<", "(")
        .replace(">", ")")
        .replace("\n", " ")
    )


def assemble_mermaid(data: dict) -> str:
    """검증 통과한 DiagramData dump → flowchart 코드. 라벨은 항상 쌍따옴표로 감싼다."""
    direction = data.get("direction") or "TD"
    lines = [f"flowchart {direction}"]
    for n in data.get("nodes") or []:
        lines.append(f'  {n["id"]}["{_escape(str(n["label"]))}"]')
    for e in data.get("edges") or []:
        label = e.get("label")
        arrow = f'-->|"{_escape(str(label))}"|' if label else "-->"
        lines.append(f'  {e["source"]} {arrow} {e["target"]}')
    return "\n".join(lines)


def edge_sentences(data: dict) -> list[str]:
    """엣지들을 사실 문장으로 직렬화 — faithfulness 대조 단위.

    다이어그램의 환각은 노드가 아니라 화살표(근거에 없는 관계 주장)에서 나오므로
    "A → B (라벨)" 문장이 정확한 검증 단위다. 기존 check_faithfulness를 재사용한다.
    """
    labels = {n["id"]: str(n["label"]) for n in data.get("nodes") or []}
    out: list[str] = []
    for e in data.get("edges") or []:
        src = labels.get(e["source"], e["source"])
        dst = labels.get(e["target"], e["target"])
        rel = f" ({e['label']})" if e.get("label") else ""
        out.append(f"{src} → {dst}{rel}")
    return out
