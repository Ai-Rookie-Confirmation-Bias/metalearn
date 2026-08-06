import { useMemo, useState } from "react";

import { CourseSelect } from "@/pages/quiz/CourseSelect";
import { ScopeSelect } from "@/pages/quiz/ScopeSelect";
import { SolveView, type SolveResult } from "@/pages/quiz/SolveView";
import { ResultView } from "@/pages/quiz/ResultView";
import {
  courseBanks,
  fetchSession,
  type CourseBank,
  type QuizStyle,
  type SessionItem,
} from "@/pages/quiz/mock";

// 문제 페이지 — 확정안 §6. 과목(책) 선택 → 범위 선택 → 풀이 → 결과.
// 문제은행이 코스 단위라 책장처럼 과목부터 고른다.
// 학습 페이지와 데이터를 공유하지 않는다(§7-③): 풀이 결과는 이 페이지 안에서만 산다.
type Step = "course" | "scope" | "solve" | "result";

export function QuizPage() {
  const [step, setStep] = useState<Step>("course");
  const [course, setCourse] = useState<CourseBank | null>(null);
  const [style, setStyle] = useState<QuizStyle>("standard"); // 기출 올린 과목만 exam 선택 가능
  const [items, setItems] = useState<SessionItem[]>([]);
  const [results, setResults] = useState<SolveResult[]>([]);
  const [lastScope, setLastScope] = useState<{ tocIndexes: number[]; count: number } | null>(null);
  const [loading, setLoading] = useState(false);

  const tocTitles = useMemo(
    () =>
      Object.fromEntries(
        (course?.summary?.tocs ?? []).map((t) => [t.toc_index, t.title]),
      ) as Record<number, string>,
    [course],
  );

  const pickCourse = (c: CourseBank, s: QuizStyle) => {
    setCourse(c);
    setStyle(s);
    setStep("scope");
  };

  const start = async (tocIndexes: number[], count: number) => {
    if (!course) return;
    setLoading(true);
    try {
      const session = await fetchSession(course.course_id, tocIndexes, count, style); // 정답 없는 문항만 도착
      setLastScope({ tocIndexes, count });
      setItems(session);
      setResults([]);
      setStep("solve");
    } finally {
      setLoading(false);
    }
  };

  const finish = (r: SolveResult[]) => {
    setResults(r);
    setStep("result");
  };

  if (step === "scope" && course?.summary)
    return (
      <div className={loading ? "pointer-events-none opacity-60" : undefined}>
        <ScopeSelect
          title={course.title}
          style={style}
          summary={course.summary}
          onStart={(t, c) => void start(t, c)}
          onBack={() => setStep("course")}
        />
      </div>
    );

  if (step === "solve")
    return (
      <SolveView key={items.map((i) => i.id).join(",")} items={items} tocTitles={tocTitles} onFinish={finish} />
    );

  if (step === "result")
    return (
      <ResultView
        results={results}
        tocTitles={tocTitles}
        onRetry={() => lastScope && void start(lastScope.tocIndexes, lastScope.count)}
        onChangeScope={() => setStep("scope")}
      />
    );

  return <CourseSelect courses={courseBanks} onSelect={pickCourse} />;
}
