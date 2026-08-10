// 몰입 학습 모드 진입점.
//
// 데이터만 모아 `FocusViewer`에 넘긴다. **셀 내용은 일반 학습 화면과 같은
// 컴포넌트**(Explanation·Figures·Cloze·Mcq)로 그린다 — 몰입 모드에서만
// 다르게 보이면 같은 자료를 두 벌 관리하는 셈이 된다.
//
// 전 화면 목록이 필요해서 목차를 전부 받는다(`useQueries`). 목차 수가 데모
// 규모(10~15)라 감당되는 비용이고, 미니맵이 전체 격자를 보여주려면 어차피
// 있어야 한다.
import { useNavigate, useParams } from "react-router-dom";
import { useQueries, useQuery } from "@tanstack/react-query";

import {
  fetchChapter,
  fetchDocument,
  type ChapterOut,
} from "@/features/curriculum/api/curriculum";
import { curriculumKeys, useAnswer, useLesson } from "@/features/curriculum/queries/useCurriculum";
import { Cloze } from "@/features/curriculum/components/Cloze";
import { Explanation } from "@/features/curriculum/components/Explanation";
import { Figures } from "@/features/curriculum/components/Figures";
import { Mcq } from "@/features/curriculum/components/Mcq";
import { FocusViewer, toColumns } from "@/features/curriculum/lesson/FocusViewer";
import { splitLesson } from "@/features/curriculum/lesson/steps";

export function FocusPage() {
  const { docId = "", sectionId = "" } = useParams();
  const navigate = useNavigate();

  const { data: doc } = useQuery({
    queryKey: curriculumKeys.document(docId),
    queryFn: () => fetchDocument(docId),
    enabled: Boolean(docId),
  });

  const chapterQueries = useQueries({
    queries: (doc?.chapters ?? []).map((ch) => ({
      queryKey: curriculumKeys.chapter(docId, ch.index),
      queryFn: () => fetchChapter(docId, ch.index),
    })),
  });
  const chapters = chapterQueries
    .map((q) => q.data)
    .filter((c): c is ChapterOut => Boolean(c));

  const { data: lesson, isLoading } = useLesson(docId, sectionId);
  const answer = useAnswer(docId);

  const columns = toColumns(chapters);
  const parts = lesson ? splitLesson(lesson) : null;

  const grade = (correct: boolean, conceptKey?: string) =>
    answer.mutate({ sectionId, correct, conceptKey });

  const exit = () =>
    navigate(`/curriculum/${encodeURIComponent(docId)}/sections/${sectionId}`);

  // 아직 목차를 못 받았으면 격자를 그릴 수 없다. 빈 화면 대신 한 줄만.
  if (!columns.length) {
    return (
      <div className="focus-root">
        <p className="fv-loading">불러오는 중…</p>
      </div>
    );
  }

  return (
    <FocusViewer
      columns={columns}
      currentSectionId={sectionId}
      onNavigate={(id) =>
        navigate(`/curriculum/${encodeURIComponent(docId)}/sections/${id}/focus`, {
          replace: true,
        })
      }
      parts={parts}
      loading={isLoading || !parts}
      renderStep={(i) => {
        const step = parts!.steps[i];
        return (
          <div className="p-8">
            {step.key && (
              <h2 className="mb-3 text-lg font-bold text-text-primary">{step.key}</h2>
            )}
            {step.explain && (
              <Explanation text={String(step.explain.content.text ?? "")} />
            )}
            {step.figures.length > 0 && <Figures figures={step.figures} />}
            {step.blocks.length > 0 && (
              <ul className="mt-4 space-y-3">
                {step.blocks.map((b, bi) => (
                  <Cloze
                    key={`${b.conceptKeys.join()}-${bi}`}
                    block={b}
                    index={step.offset + bi + 1}
                    onGraded={grade}
                  />
                ))}
              </ul>
            )}
          </div>
        );
      }}
      renderTail={() =>
        parts?.mcq ? (
          <div className="p-8">
            <h2 className="mb-3 text-lg font-bold text-text-primary">
              섞어서 구별하기
            </h2>
            <ul>
              <Mcq block={parts.mcq} onGraded={grade} />
            </ul>
          </div>
        ) : null
      }
      onExit={exit}
    />
  );
}
