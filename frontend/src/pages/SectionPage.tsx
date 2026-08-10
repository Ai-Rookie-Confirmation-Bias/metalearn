// [화면 3] 절 하나 — 읽고, 바로 꺼낸다.
//
// "읽게 하지 않고 꺼내게 한다"가 서비스 정의라 설명 뒤에 인출이 반드시 붙는다.
// 빈칸은 회상(이 개념을 꺼낼 수 있나), 객관식은 구별(개념 사이를 가를 수 있나)로
// 목적이 다르므로 화면에서도 나눠 보여준다.
//
// 📎 원문은 **요약이 아니라 교재 그대로**다. 요약을 넣으면 그것도 AI 생성물이 되어
// "AI가 지어낸 해설이 아니라 교재의 그 문장"이라는 근거가 무너진다.
import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import type { BlockOut } from "@/features/curriculum/api/curriculum";
import { Cloze } from "@/features/curriculum/components/Cloze";
import { Explanation } from "@/features/curriculum/components/Explanation";
import { Figures } from "@/features/curriculum/components/Figures";
import { Mcq } from "@/features/curriculum/components/Mcq";
import { Reason, StatusBadge } from "@/features/curriculum/components/bits";
import { splitLesson } from "@/features/curriculum/lesson/steps";
import { useAnswer, useLesson } from "@/features/curriculum/queries/useCurriculum";

/** ⚡ 지난 결손을 짚는 자리 — 한 문단은 그냥 보이고, 다시 설명은 **펼쳐야** 보인다.
 *
 * 팝업으로 띄우지 않는다. 화면에 들어오자마자 "앞에서 틀렸어요"라고 물으면
 * 학습자는 아직 아무것도 안 읽어서 필요한지 판단할 근거가 없다. 문맥이 깔린
 * 이 자리에 접어두면, 안 눌러도 흐름이 안 끊기고 누르는 건 진짜 선택이 된다.
 *
 * ⚠️ 펼쳤다는 것 자체는 **숙련도에 기록하지 않는다.** 문항을 틀린 게 아니라
 *    "다시 봤다"일 뿐인데 정답률에 섞으면 오측정이다. 아래 빈칸 결과만 올린다.
 */
function TieIn({
  block,
  tiedIn,
  onGraded,
}: {
  block: BlockOut;
  tiedIn: string[];
  onGraded: (correct: boolean, conceptKey?: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const more = String(block.content.more ?? "");
  const cloze = block.content.cloze as BlockOut["content"] | undefined;

  return (
    <div className="mb-8 rounded-lg border-l-4 border-accent bg-accent/5 p-4">
      <p className="text-[0.7rem] font-semibold text-accent">
        ⚡ {String(block.content.label ?? "여기서 잠깐")} —{" "}
        {tiedIn.join(" · ")}을(를) 최근 틀리셔서 여기에 엮었습니다
      </p>
      <p className="mt-1 leading-relaxed text-text-primary">
        {String(block.content.text ?? "")}
      </p>

      {/* 본문이 없으면 버튼도 없다 — 빈 서랍을 열게 하지 않는다. */}
      {more && !open && (
        <button
          type="button"
          onClick={() => setOpen(true)}
          className="mt-3 text-[0.8rem] font-semibold text-accent hover:underline"
        >
          {tiedIn[0]} 다시 설명 보기 ▾
        </button>
      )}

      {more && open && (
        <div className="mt-3 border-t border-accent/20 pt-3">
          <p className="whitespace-pre-line leading-relaxed text-text-primary">{more}</p>
          {/* 읽고 끝내면 "봤다"는 느낌만 남는다. 읽었으면 바로 꺼내본다. */}
          {cloze && (
            <ul className="mt-4">
              <Cloze
                block={{ type: "cloze", content: cloze, conceptKeys: [tiedIn[0]] }}
                index={1}
                onGraded={onGraded}
              />
            </ul>
          )}
        </div>
      )}
    </div>
  );
}

export function SectionPage() {
  const { docId = "", sectionId = "" } = useParams<{ docId: string; sectionId: string }>();
  const { data, isLoading, isError } = useLesson(docId, sectionId);
  const answer = useAnswer(docId);
  const [showSource, setShowSource] = useState(false);

  if (isLoading)
    return (
      <div className="mx-auto max-w-2xl p-8">
        <p className="text-text-secondary">학습 내용을 만드는 중…</p>
        <p className="mt-1 text-[0.8rem] text-text-tertiary">
          이 화면은 처음이라 5~10초 걸립니다. 다음부터는 바로 열립니다.
        </p>
      </div>
    );
  if (isError || !data)
    return <p className="p-8 text-red-600">학습 내용을 불러오지 못했습니다.</p>;

  // 개념 단위로 자르는 규칙은  한 곳에 있다 — 몰입 뷰어가
  // 같은 함수를 쓴다. 두 화면이 각자 자르면 같은 자료인데 순서가 달라진다.
  const { steps, looseExplain, analogy, tieIn, mcq } = splitLesson(data);

  const grade = (correct: boolean, conceptKey?: string) =>
    answer.mutate({ sectionId, correct, conceptKey });

  return (
    <div className="mx-auto max-w-2xl p-8">
      <div className="flex items-center justify-between gap-3">
        <Link
          to={`/curriculum/${encodeURIComponent(docId)}/chapters/${data.chapterIndex}`}
          className="text-[0.8rem] text-text-tertiary hover:underline"
        >
          ← {data.chapterTitle}
        </Link>
        {/* 몰입 모드 — 한 번에 개념 하나만. 나머지 UI를 다 걷어낸다. */}
        <Link
          to={`/curriculum/${encodeURIComponent(docId)}/sections/${sectionId}/focus`}
          className="inline-flex items-center gap-1.5 rounded-lg border border-border-primary px-3 py-1.5 text-[0.78rem] font-semibold text-text-secondary transition-colors hover:border-accent hover:bg-accent/5 hover:text-accent"
        >
          🎧 몰입 모드
        </Link>
      </div>

      <header className="mt-3 mb-6">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-[0.7rem] font-semibold text-text-tertiary">화면</p>
            <h1 className="text-2xl font-bold text-text-primary">{data.title}</h1>
          </div>
          <StatusBadge status={data.status} label={data.statusLabel} />
        </div>
        <p className="mt-2 text-[0.75rem] text-text-tertiary">
          이 화면에서 배우는 개념 {data.concepts.length}개
          {data.page && <> · 📖 {data.page}</>}
        </p>
        <p className="mt-0.5 text-[0.8rem] text-text-secondary">
          {data.concepts.join(" · ")}
        </p>
        <div className="mt-2">
          <Reason text={data.reason} />
        </div>
      </header>

      {!data.generated && (
        <p className="rounded-lg bg-red-50 p-4 text-sm text-red-700">
          학습 내용을 만들지 못했습니다. 잠시 후 다시 열어주세요.
        </p>
      )}

      {analogy && (
        <div className="mb-5 rounded-lg bg-amber-50/70 p-4">
          <p className="text-[0.7rem] font-semibold text-amber-700">
            💡 {String(analogy.content.label ?? "비유")}
          </p>
          <p className="mt-1 leading-relaxed text-text-primary">
            {String(analogy.content.text ?? "")}
          </p>
        </div>
      )}

      {/* 개념에 못 붙은 설명(옛 응답 · 이름 불일치). 앞에 그대로 둔다. */}
      {looseExplain.map((b, i) => (
        <Explanation key={`loose-${i}`} text={String(b.content.text ?? "")} />
      ))}

      {tieIn && <TieIn block={tieIn} tiedIn={data.tiedIn} onGraded={grade} />}

      {/* ★ 개념 단위로 끊어 낸다.
          전에는 설명 한 덩어리 뒤에 빈칸을 몰아 놨는데, 그러면 "읽고 바로
          꺼낸다"는 우리 주장과 화면이 어긋난다 — 셋을 다 읽고 나서 셋을 몰아
          답하는 건 그냥 시험이다. 개념마다 물음을 붙이면 읽은 직후에 꺼낸다.

          conceptKeys가 하나인 빈칸만 개념에 귀속시킨다. 여럿이거나 없는 것은
          (성질 문항 등) 맨 끝 묶음으로 간다 — 어느 개념 것인지 모르는 걸
          임의로 배정하면 학습자가 엉뚱한 순서로 읽는다. */}
      {steps.length > 0 && (
        <section className="mb-8">
          <div className="space-y-10">
            {steps.map((step, si) => (
              <div key={step.key ?? `rest-${si}`}>
                {step.key && (
                  <h2 className="mb-2 border-b border-border-primary pb-1.5 text-[0.95rem] font-bold text-text-primary">
                    {step.key}
                  </h2>
                )}

                {step.explain && (
                  <Explanation text={String(step.explain.content.text ?? "")} />
                )}

                {/* 그림은 **있을 때만** 자리를 차지한다. 개념마다 빈 칸을
                    남겨 두면 화면이 성기게 보인다. */}
                {step.figures.length > 0 && <Figures figures={step.figures} />}

                {step.blocks.length > 0 && (
                  <div className="rounded-xl border border-border-primary bg-white p-4">
                    <p className="mb-2.5 text-[0.78rem] font-bold text-accent">
                      꺼내보기 — 설명을 덮고 답해보세요
                    </p>
                    <ul className="space-y-3">
                      {step.blocks.map((b, i) => (
                        <Cloze
                          key={`${b.conceptKeys.join()}-${i}`}
                          block={b}
                          index={step.offset + i + 1}
                          onGraded={grade}
                        />
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            ))}

            {mcq && (
              <div className="rounded-xl border border-border-primary bg-white p-4">
                <p className="mb-2.5 text-[0.78rem] font-bold text-text-secondary">
                  섞어서 구별하기
                </p>
                <ul>
                  <Mcq block={mcq} onGraded={grade} />
                </ul>
              </div>
            )}
          </div>
        </section>
      )}

      {data.source && (
        <section className="border-t border-border-primary pt-4">
          <button
            type="button"
            onClick={() => setShowSource((v) => !v)}
            className="text-[0.8rem] font-medium text-text-secondary hover:underline"
          >
            📎 교재 원문 {data.page && `(${data.page})`} {showSource ? "접기" : "펼치기"}
          </button>
          {showSource && (
            <pre className="mt-3 overflow-x-auto rounded-lg bg-bg-secondary p-4 text-[0.78rem] leading-relaxed whitespace-pre-wrap text-text-secondary">
              {data.source}
            </pre>
          )}
          <p className="mt-2 text-[0.72rem] text-text-tertiary">
            요약이 아니라 교재에 있는 그대로입니다.
          </p>
        </section>
      )}
    </div>
  );
}
