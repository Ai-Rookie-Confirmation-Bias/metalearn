// 책 표지(색+아이콘). **표현 계층이다** — 서버는 색을 모른다.
//
// docId로 파생해 같은 책이 늘 같은 표지를 갖게 하고, 한 화면 안에서는 서로
// 안 겹치게 민다. 책장과 기본 제공 자료 두 페이지가 같이 쓴다.
import {
  PencilIcon,
  BookOpenIcon,
  PenNibIcon,
  NotebookIcon,
  GraduationCapIcon,
  BookmarkIcon,
  type Icon,
} from "@phosphor-icons/react";

export type Cover = { grad: string; icon: Icon };

export const COVERS: Cover[] = [
  { grad: "from-[#0f172a] to-[#334155]", icon: PencilIcon },
  { grad: "from-[#059669] to-[#10b981]", icon: BookOpenIcon },
  { grad: "from-[#7c3aed] to-[#a855f7]", icon: PenNibIcon },
  { grad: "from-[#d97706] to-[#f59e0b]", icon: NotebookIcon },
  { grad: "from-[#e11d48] to-[#fb7185]", icon: GraduationCapIcon },
  { grad: "from-[#0d9488] to-[#14b8a6]", icon: BookmarkIcon },
];

function hashIndex(id: string) {
  return [...id].reduce((sum, ch) => sum + ch.charCodeAt(0), 0) % COVERS.length;
}

export function assignCovers(ids: string[]): Map<string, Cover> {
  const used = new Set<number>();
  const map = new Map<string, Cover>();
  for (const id of ids) {
    let idx = hashIndex(id);
    for (let i = 0; used.has(idx) && i < COVERS.length; i++) {
      idx = (idx + 1) % COVERS.length;
    }
    used.add(idx);
    map.set(id, COVERS[idx]);
  }
  return map;
}
