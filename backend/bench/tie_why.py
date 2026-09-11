"""① 판정이 선수관계 때문인지 분류어 때문인지 나눠 본다. 오판을 찾는 게 목적."""
import sys
from pathlib import Path

sys.path.insert(0, "/app")

from app.features.curriculum.excerpt import category_words  # noqa: E402
from app.features.curriculum.store import build_document  # noqa: E402

for name in ("파싱결과_필기핵심요약", "파싱결과_실기요약노트"):
    doc = build_document(Path(f"/app/tests/fixtures/{name}.md"))
    sections = [s for ch in doc.chapters for s in ch.sections]
    all_keys = [k for s in sections for k in s.concept_keys]
    cats = category_words(all_keys, min_share=2)
    print(f"## {name}  절 {len(sections)} · 분류어 {len(cats)}개")

    n_pre = n_cat = 0
    pre_ex, cat_ex = [], []
    for i, s in enumerate(sections):
        if i == 0:
            continue
        wrong = sections[i - 1].concept_keys[0]
        if wrong in s.concept_keys:
            continue
        prereq = {p for c in s.concepts for p in c.prerequisites}
        linked = wrong in prereq or any(wrong in c.prerequisites for c in s.concepts)

        def tail(k):
            p = k.split()
            return p[-1] if len(p) >= 2 and p[-1] in cats else ""

        shares = bool(tail(wrong)) and tail(wrong) in {
            t for k in s.concept_keys if (t := tail(k))
        }
        if linked:
            n_pre += 1
            if len(pre_ex) < 6:
                pre_ex.append(f"{wrong} → {s.title}")
        if shares:
            n_cat += 1
            if len(cat_ex) < 6:
                cat_ex.append(f"{wrong} → {s.title}  [{tail(wrong)}]")

    print(f"   ① 선수관계로 걸림 {n_pre}")
    for x in pre_ex:
        print(f"        {x}")
    print(f"   ② 분류어 공유로 걸림 {n_cat}")
    for x in cat_ex:
        print(f"        {x}")
    print()
