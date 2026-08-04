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
import { Reason, StatusBadge } from "@/features/curriculum/components/bits";
import { useAnswer, useLesson } from "@/features/curriculum/queries/useCurriculum";

/** 채점은 공백·대소문자만 흡수한다. 그 이상 느슨하게 하면 인출이 아니게 된다. */
const norm = (s: string) => s.replace(/\s+/g, "").toLowerCase();

function Cloze({
  block,
  index,
  onGraded,
}: {
  block: BlockOut;
  index: number;
  onGraded: (correct: boolean, conceptKey?: string) => void;
}) {
  const sentence = String(block.content.sentence ?? "");
  const answer = String(block.content.answer ?? "");
  const [value, setValue] = useState("");
  const [graded, setGraded] = useState<boolean | null>(null);

  const check = () => {
    if (graded !== null || !value.trim()) return;
    const ok = norm(value) === norm(answer);
    setGraded(ok);
    // 개념이 하나로 특정될 때만 그 개념에 기록한다. 여럿이면(라벨을 못 붙인 경우)
    // 절 단위로만 센다 — 첫 개념에 몰아주면 약점 통계가 통째로 거짓이 된다.
    onGraded(ok, block.conceptKeys.length === 1 ? block.conceptKeys[0] : undefined);
  };

  const [before, after] = sentence.split("____");
  return (
    <li className="rounded-lg border border-border-primary p-4">
      <p className="text-[0.7rem] font-semibold text-text-tertiary">빈칸 {index}</p>
      <p className="mt-1 leading-relaxed text-text-primary">
        {before}
        <span className="mx-1 inline-block min-w-[5rem] border-b-2 border-accent text-center font-semibold text-accent">
          {graded !== null ? answer : "　　　"}
        </span>
        {after}
      </p>

      {graded === null ? (
        <div className="mt-3 flex gap-2">
          <input
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && check()}
            placeholder="답을 적어보세요"
            className="flex-1 rounded border border-border-primary px-3 py-1.5 text-sm outline-none focus:border-accent"
          />
          <button
            type="button"
            onClick={check}
            className="rounded bg-primary px-3 py-1.5 text-sm font-medium text-white hover:bg-primary-hover"
          >
            확인
          </button>
        </div>
      ) : (
        <p
          className={`mt-2 text-sm font-semibold ${graded ? "text-emerald-600" : "text-red-600"}`}
        >
          {graded ? "✓ 맞았습니다" : `✗ 정답은 "${answer}" 입니다`}
          {!graded && value && (
            <span className="ml-1 font-normal text-text-tertiary">(적은 답: {value})</span>
          )}
        </p>
      )}
    </li>
  );
}

function Mcq({
  block,
  onGraded,
}: {
  block: BlockOut;
  onGraded: (correct: boolean, conceptKey?: string) => void;
}) {
  const question = String(block.content.question ?? "");
  const options = (block.content.options as string[]) ?? [];
  const answer = String(block.content.answer ?? "");
  const explanation = String(block.content.explanation ?? "");
  const [picked, setPicked] = useState<string | null>(null);

  // 객관식은 여러 개념을 구별하는 문항이라 conceptKeys가 절 전체다.
  // **채점 귀속에 conceptKeys[0]을 쓰면 안 된다** — 항상 첫 개념에 몰린다(실측 5/5 오귀속).
  // 백엔드가 "이 문항이 실제로 묻는 개념"을 content.concept로 실어 보낸다.
  const target = (block.content.concept as string | null) ?? undefined;

  const pick = (o: string) => {
    if (picked !== null) return;
    setPicked(o);
    onGraded(o === answer, target);
  };

  return (
    <li className="rounded-lg border border-border-primary p-4">
      <p className="text-[0.7rem] font-semibold text-text-tertiary">
        구별하기 — 헷갈리는 지점
      </p>
      <p className="mt-1 leading-relaxed font-medium text-text-primary">{question}</p>
      <ul className="mt-3 space-y-1.5">
        {options.map((o) => {
          const isAnswer = o === answer;
          const chosen = picked === o;
          const done = picked !== null;
          return (
            <li key={o}>
              <button
                type="button"
                disabled={done}
                onClick={() => pick(o)}
                className={[
                  "w-full rounded border px-3 py-2 text-left text-sm transition-colors",
                  !done && "border-border-primary hover:bg-bg-secondary",
                  done && isAnswer && "border-emerald-400 bg-emerald-50 font-semibold",
                  done && chosen && !isAnswer && "border-red-400 bg-red-50",
                  done && !isAnswer && !chosen && "border-border-primary opacity-50",
                ]
                  .filter(Boolean)
                  .join(" ")}
              >
                {done && isAnswer && "✓ "}
                {done && chosen && !isAnswer && "✗ "}
                {o}
              </button>
            </li>
          );
        })}
      </ul>
      {picked !== null && explanation && (
        <p className="mt-3 text-sm leading-relaxed text-text-secondary">{explanation}</p>
      )}
    </li>
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
          이 절은 처음이라 5~10초 걸립니다. 다음부터는 바로 열립니다.
        </p>
      </div>
    );
  if (isError || !data)
    return <p className="p-8 text-red-600">학습 내용을 불러오지 못했습니다.</p>;

  const explanation = data.blocks.find((b) => b.type === "concept");
  const analogy = data.blocks.find((b) => b.type === "analogy");
  const clozes = data.blocks.filter((b) => b.type === "cloze");
  const mcq = data.blocks.find((b) => b.type === "mcq");

  const grade = (correct: boolean, conceptKey?: string) =>
    answer.mutate({ sectionId, correct, conceptKey });

  return (
    <div className="mx-auto max-w-2xl p-8">
      <Link
        to={`/curriculum/${encodeURIComponent(docId)}/chapters/${data.chapterIndex}`}
        className="text-[0.8rem] text-text-tertiary hover:underline"
      >
        ← {data.chapterTitle}
      </Link>

      <header className="mt-3 mb-6">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-[0.7rem] font-semibold text-text-tertiary">절</p>
            <h1 className="text-2xl font-bold text-text-primary">{data.title}</h1>
          </div>
          <StatusBadge status={data.status} label={data.statusLabel} />
        </div>
        <p className="mt-2 text-[0.75rem] text-text-tertiary">
          이 절에서 배우는 개념 {data.concepts.length}개
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

      {explanation && (
        <article className="mb-8 leading-loose whitespace-pre-line text-text-primary">
          {String(explanation.content.text ?? "")}
        </article>
      )}

      {(clozes.length > 0 || mcq) && (
        <section className="mb-8">
          <h2 className="mb-1 text-sm font-bold text-text-primary">꺼내보기</h2>
          <p className="mb-3 text-[0.8rem] text-text-tertiary">
            설명을 덮고 답해보세요. 읽는 것보다 꺼내는 게 훨씬 오래 남습니다.
          </p>
          <ul className="space-y-3">
            {clozes.map((b, i) => (
              <Cloze
                key={`${b.conceptKeys.join()}-${i}`}
                block={b}
                index={i + 1}
                onGraded={grade}
              />
            ))}
            {mcq && <Mcq block={mcq} onGraded={grade} />}
          </ul>
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
