// 초안 → 코스. **책장이 파싱을 지켜보다가 다 끝나면 만든다.**
//
// 위저드에서 만들 수 없는 이유는 서버 쪽에 있다. `POST /courses`가 그 자리에서
// 뼈대의 목차를 복사하고 밀도로 역할을 정하는데, 둘 다 파싱이 끝나야 생기는
// 값이라 그전에 부르면 목차 0개짜리 코스가 만들어진다. 파이프라인이 분 단위라
// 위저드에 사용자를 붙잡아 둘 수도 없다.
//
// 그래서 위저드는 초안만 남기고, 책장이 이 훅으로 마무리한다.
import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { createCourse } from "@/features/course/api";
import { useCourseDrafts, userId, type CourseDraft } from "@/features/course/store";
import { curriculumKeys } from "@/features/curriculum/queries/useCurriculum";
import type { ParseStatus } from "@/features/parsing/api/documents";
import { useParsingDocuments } from "@/features/parsing/queries/useParsingDocuments";

export type DraftView = CourseDraft & {
  /** 이 초안이 기다리는 자료들의 파싱 상태. */
  statuses: (ParseStatus | undefined)[];
  ready: boolean;
  failed: boolean;
  /** 코스를 만드는 중이거나 만들다 실패했나. */
  creating: boolean;
  error?: string;
};

function describe(error: unknown): string {
  const detail = (error as { response?: { data?: { detail?: string } } })?.response
    ?.data?.detail;
  return detail ?? (error as Error)?.message ?? String(error);
}

export function useDraftCourses(): DraftView[] {
  const qc = useQueryClient();
  const drafts = useCourseDrafts((s) => s.drafts);
  const patch = useCourseDrafts((s) => s.patch);

  // 아직 코스가 안 된 초안이 기다리는 자료들만 폴링한다.
  const waiting = drafts.filter((d) => !d.courseId);
  const docIds = [...new Set(waiting.flatMap((d) => d.docIds))];
  const queries = useParsingDocuments(docIds);

  const statusOf = new Map<string, ParseStatus | undefined>();
  docIds.forEach((id, i) => statusOf.set(id, queries[i]?.data?.status));

  // **한 번만 만든다.** 폴링이 2초마다 돌고 상태가 여러 번 바뀌므로,
  // store에 courseId가 박히기 전에 두 번 부를 수 있다.
  const claimed = useRef(new Set<string>());
  const [busy, setBusy] = useState<Record<string, boolean>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    for (const draft of drafts) {
      if (draft.courseId || claimed.current.has(draft.id)) continue;
      const all = draft.docIds.map((id) => statusOf.get(id));
      if (!all.every((s) => s === "ready")) continue;

      claimed.current.add(draft.id);
      setBusy((b) => ({ ...b, [draft.id]: true }));
      createCourse({
        user_id: userId(),
        document_ids: draft.docIds,
        title: draft.title,
      })
        .then((course) => {
          patch(draft.id, { courseId: course.id });
          // 코스가 생기면 책장 목록이 바뀐다 — 코스 한 권이 뜨고 거기 묶인
          // 자료들은 목록에서 빠진다(같은 내용이 두 권으로 뜨면 안 된다).
          return qc.invalidateQueries({ queryKey: curriculumKeys.documents });
        })
        .catch((e) => {
          claimed.current.delete(draft.id); // 다음 폴링에서 다시 시도한다
          setErrors((s) => ({ ...s, [draft.id]: describe(e) }));
        })
        .finally(() => setBusy((b) => ({ ...b, [draft.id]: false })));
    }
    // statusOf는 매 렌더 새 Map이라 의존성에 못 넣는다. 상태 문자열로 대신한다.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [drafts, docIds.map((id) => statusOf.get(id)).join(","), patch, qc]);

  return drafts.map((draft) => {
    const statuses = draft.docIds.map((id) => statusOf.get(id));
    return {
      ...draft,
      statuses,
      ready: statuses.every((s) => s === "ready"),
      failed: statuses.some((s) => s === "failed"),
      creating: Boolean(busy[draft.id]),
      error: errors[draft.id],
    };
  });
}
