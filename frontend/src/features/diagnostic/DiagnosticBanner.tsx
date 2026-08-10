// 자료 개요 위에 뜨는 진단 안내.
//
// **코스일 때만 뜬다.** 선수 개념이 코스 층에서 나오므로 자료 하나짜리에는
// 진단이 없다 — 그 경우 서버가 404를 주고 이 배너는 아무것도 안 그린다.
// 링크를 항상 보여주고 눌러서 실패하게 두는 것보다, 있을 때만 보이는 쪽이 낫다.
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { CompassIcon } from "@phosphor-icons/react";

import { fetchSetup } from "@/features/diagnostic/api";

export function DiagnosticBanner({ docId }: { docId: string }) {
  const { data } = useQuery({
    queryKey: ["diagnostic", "setup", docId],
    queryFn: () => fetchSetup(docId),
    // 자료 하나면 404다. 정상이므로 재시도하지 않고 조용히 넘어간다.
    retry: false,
    enabled: Boolean(docId),
  });

  if (!data) return null;

  // 이미 진단을 마쳤으면 **다시 하는 문을 안 준다.** 진단은 목차를 정하는
  // 단계라, 이미 배우기 시작한 뒤에 다시 돌리면 읽던 단원 앞뒤가 바뀐다.
  // 대신 결과를 언제든 다시 볼 수 있게 한다.
  if (data.diagnosed_at) {
    return (
      <Link
        to={`/curriculum/${encodeURIComponent(docId)}/diagnostic-report`}
        className="mb-4 inline-block text-[0.8rem] text-text-tertiary hover:underline"
      >
        📋 진단 리포트 보기
      </Link>
    );
  }

  return (
    <Link
      to={`/diagnostic/${encodeURIComponent(docId)}`}
      className="mb-6 flex items-center gap-4 rounded-2xl border border-accent/30 bg-accent/5 px-6 py-5 transition-colors hover:bg-accent/10"
    >
      <CompassIcon className="shrink-0 text-[1.75rem] text-accent" weight="duotone" />
      <div className="min-w-0">
        <div className="font-bold text-text-primary">시작 전에 몇 가지만 여쭤볼게요</div>
        <div className="mt-0.5 text-[0.88rem] text-text-secondary">
          시험이 아니에요. 아는 것은 설명을 줄이고 모르는 것은 먼저 채우려고 묻습니다.
        </div>
      </div>
      <span className="ml-auto shrink-0 rounded-xl bg-accent px-5 py-2 text-[0.85rem] font-semibold text-white">
        진단하기
      </span>
    </Link>
  );
}
