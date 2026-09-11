"""약점 배선 실측 — 틀린 개념이 다음 절 설명에 실제로 들어가는가.

확인하는 것 넷:
  ① 관련성 규칙이 절을 제대로 고르는가 (LLM 없이, 전 절 대상)
  ② 실제 생성에서 tie_in 문단이 나오는가
  ③ 무관한 약점을 줬을 때는 안 나오는가 (억지로 안 엮는가)
  ④ 캐시가 약점을 구분하는가
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, "/app")

from app.features.curriculum.blocks import ConceptBrief  # noqa: E402,F401
from app.features.curriculum.planner import weak_for_section  # noqa: E402
from app.features.curriculum.service import build_lesson  # noqa: E402
from app.features.curriculum.store import build_document  # noqa: E402

MD = Path("/app/tests/fixtures/파싱결과_필기핵심요약.md")


def body(lesson, kind: str) -> str:
    return next((b.content["text"] for b in lesson.blocks if b.type == kind), "")


def main() -> None:
    doc = build_document(MD)
    sections = [s for ch in doc.chapters for s in ch.sections]
    all_keys = [k for s in sections for k in s.concept_keys]
    print(f"절 {len(sections)}개 · 개념 {len(all_keys)}개\n")

    # ① 규칙이 얼마나 자주 걸리는가. 각 절 앞의 개념 하나를 "틀렸다"고 두고 본다.
    hit = 0
    samples = []
    for i, s in enumerate(sections):
        if i == 0:
            continue
        wrong = [sections[i - 1].concept_keys[0]]
        w = weak_for_section(s, wrong, all_keys)
        if w:
            hit += 1
            if len(samples) < 8:
                samples.append((wrong[0], s.title))
    print(f"① 직전 절 개념을 틀렸을 때 이어짐 판정: {hit}/{len(sections)-1}")
    for wrong, title in samples:
        print(f"     '{wrong}' 틀림 → 절 '{title}'")

    # ② 이어진다고 판정된 첫 절로 실제 생성
    target = None
    for i, s in enumerate(sections):
        if i == 0:
            continue
        w = weak_for_section(s, [sections[i - 1].concept_keys[0]], all_keys)
        if w and len(s.concepts) >= 3:
            target = (s, w)
            break
    if target is None:
        print("\n② 이어지는 절을 못 찾음")
        return
    sec, weak = target
    print(f"\n② 절 '{sec.title}' · 개념 {list(sec.concept_keys)}")
    print(f"   녹일 약점: {weak}")

    lesson = asyncio.run(build_lesson(sec, "", weak, refresh=True))
    text, tie = body(lesson, "concept"), body(lesson, "tie_in")
    print(f"   본문 {len(text)}자 · 개념 커버 {lesson.covered}/{len(sec.concepts)}")
    print(f"   tie_in 블록 {bool(tie)} · tied_in {lesson.tied_in}")
    if tie:
        print(f"   >>> {tie.strip()[:300]}")

    # ③ 무관한 약점 — 억지로 엮지 않아야 한다
    unrelated = next(
        (k for k in all_keys if k not in sec.concept_keys and " " not in k), all_keys[0]
    )
    print(f"\n③ 무관한 약점 '{unrelated}' 강제 주입")
    l2 = asyncio.run(build_lesson(sec, "", (unrelated,), refresh=True))
    t2 = body(l2, "tie_in")
    print(f"   tie_in 블록 {bool(t2)} · tied_in {l2.tied_in}")
    if t2:
        print(f"   >>> {t2.strip()[:300]}")

    # ④ 캐시가 약점을 구분하는가
    a = asyncio.run(build_lesson(sec, "", weak))
    b = asyncio.run(build_lesson(sec, "", ()))
    again = asyncio.run(build_lesson(sec, "", weak))
    print(f"\n④ 약점 유무로 다른 글: {body(a,'concept') != body(b,'concept')}")
    print(f"   같은 약점이면 같은 글: {body(a,'concept') == body(again,'concept')}")
    print(f"   약점 없을 때 tie_in 없음: {not body(b,'tie_in')}")


if __name__ == "__main__":
    main()
