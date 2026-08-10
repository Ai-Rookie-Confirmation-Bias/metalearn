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
import { Link, Navigate, Outlet, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeftIcon } from "@phosphor-icons/react";

import { listCourses } from "@/features/course/api";
import { OutlinePanel } from "@/features/curriculum/components/OutlinePanel";
import { useDocument } from "@/features/curriculum/queries/useCurriculum";

export function CurriculumLayout() {
  const { docId = "" } = useParams<{ docId: string }>();
  const { data } = useDocument(docId);

  // **진단 전에는 못 들어온다.** 진단은 목차를 *정하는* 단계다 — 보강 단원이
  // 목차 앞에 끼워지므로, 먼저 읽고 나서 하면 이미 읽은 단원 앞에 끼워진다
  // (실측: 목차 5 → 12). 책장 카드는 이미 진단으로 보내지만 뒤로 가기·북마크·
  // 주소 직접 입력이 그 문을 우회한다. 문은 여기 하나로 잠근다.
  //
  // 코스 목록이 답이다 — 픽스처·자료 하나는 이 목록에 없으므로 그대로 통과한다.
  const { data: courses, isLoading } = useQuery({
    queryKey: ["courses", "list"],
    queryFn: listCourses,
    staleTime: 10_000,
  });
  const course = courses?.find((c) => c.id === docId);

  // 목록을 못 받았으면 **막지 않는다.** 서버가 잠깐 흔들렸다는 이유로 학습을
  // 못 하게 하는 쪽이 진단을 한 번 건너뛰는 것보다 나쁘다.
  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center bg-bg-secondary text-text-secondary">
        불러오는 중…
      </div>
    );
  }
  if (course && !course.diagnosed_at) {
    return <Navigate to={`/diagnostic/${encodeURIComponent(docId)}`} replace />;
  }

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
