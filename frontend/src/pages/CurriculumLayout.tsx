// 커리큘럼 셸 — 좌측에 목차를 고정하고 본문만 바꾼다.
//
// 자료 → 목차 → 화면을 전체 페이지로 넘나들면 매번 "지금 어디인지"가 사라지고,
// 다음 화면으로 가려면 뒤로 → 목록 → 클릭을 반복해야 한다. 목차를 옆에 두면
// 이동이 한 번에 끝난다.
//
// 좁은 화면에서는 목차를 감춘다(`lg:flex`). 그때는 원래대로 목록 페이지를 거쳐
// 이동하면 되고, 기능이 사라지지는 않는다.
//
// ★ 이 셸은 글로벌 사이드바 **밖**이다(`routes.tsx` 참조). 그래서 나가는 길을
//   여기가 책임진다 — 목차는 `lg` 미만에서 숨으므로 헤더가 없으면 좁은 화면에서
//   나갈 방법이 하나도 없다. 학습을 막지 않는다는 원칙은 "못 나간다"에도 걸린다.
import { Link, Outlet, useParams } from "react-router-dom";
import { ArrowLeftIcon } from "@phosphor-icons/react";

import { OutlinePanel } from "@/features/curriculum/components/OutlinePanel";
import { useDocument } from "@/features/curriculum/queries/useCurriculum";

export function CurriculumLayout() {
  const { docId = "" } = useParams<{ docId: string }>();
  const { data } = useDocument(docId);

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-bg-secondary">
      <header className="flex h-14 flex-shrink-0 items-center gap-3 border-b border-border-primary bg-white px-5">
        <Link
          to="/library"
          className="flex items-center gap-1.5 text-[0.85rem] font-semibold text-text-secondary transition-colors hover:text-accent"
        >
          <ArrowLeftIcon className="text-[1rem]" />
          나의 책장
        </Link>
        {/* 목차가 숨는 좁은 화면에서는 여기가 유일한 "어느 자료인지" 표시다. */}
        <span className="min-w-0 truncate text-[0.9rem] font-bold text-text-primary lg:hidden">
          📚 {data?.title ?? ""}
        </span>
      </header>

      <div className="flex min-h-0 flex-1">
        <OutlinePanel docId={docId} />
        <div className="min-w-0 flex-1 overflow-y-auto">
          <Outlet />
        </div>
      </div>
    </div>
  );
}
