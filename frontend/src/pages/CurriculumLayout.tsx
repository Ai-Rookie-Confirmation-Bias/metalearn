// 커리큘럼 셸 — 좌측에 목차를 고정하고 본문만 바꾼다.
//
// 자료 → 목차 → 화면을 전체 페이지로 넘나들면 매번 "지금 어디인지"가 사라지고,
// 다음 화면으로 가려면 뒤로 → 목록 → 클릭을 반복해야 한다. 목차를 옆에 두면
// 이동이 한 번에 끝난다.
//
// 좁은 화면에서는 목차를 감춘다(`lg:flex`). 그때는 원래대로 목록 페이지를 거쳐
// 이동하면 되고, 기능이 사라지지는 않는다.
import { Outlet, useParams } from "react-router-dom";

import { OutlinePanel } from "@/features/curriculum/components/OutlinePanel";

export function CurriculumLayout() {
  const { docId = "" } = useParams<{ docId: string }>();

  return (
    <div className="flex h-full min-h-0">
      <OutlinePanel docId={docId} />
      <div className="min-w-0 flex-1 overflow-y-auto">
        <Outlet />
      </div>
    </div>
  );
}
