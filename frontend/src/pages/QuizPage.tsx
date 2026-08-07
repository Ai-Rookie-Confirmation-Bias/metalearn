import { useEffect, useMemo, useState } from "react";

import { CourseSelect } from "@/pages/quiz/CourseSelect";
import { ScopeSelect } from "@/pages/quiz/ScopeSelect";
import { SolveView, type SolveResult } from "@/pages/quiz/SolveView";
import { ResultView } from "@/pages/quiz/ResultView";
import { fetchCourseBanks, fetchSession } from "@/pages/quiz/api";
import type { CourseBank, QuizStyle, SessionItem } from "@/pages/quiz/mock";

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

  // 과목 목록 — 서버의 코스 + 문제은행 요약 (mock 시절 courseBanks 하드코딩 대체)
  const [banks, setBanks] = useState<CourseBank[] | null>(null); // null = 로딩 중
  const [loadError, setLoadError] = useState(false);
  useEffect(() => {
    let alive = true;
    fetchCourseBanks()
      .then((b) => alive && setBanks(b))
      .catch(() => alive && setLoadError(true));
    return () => {
      alive = false;
    };
  }, []);

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
    if (!course?.summary) return;
    setLoading(true);
    try {
      // 정답 없는 문항만 도착. style은 기출 백엔드(§3.6) 전이라 아직 안 보낸다.
      const session = await fetchSession(
        course.course_id,
        course.summary.document_id,
        tocIndexes,
        count,
      );
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

  if (loadError)
    return (
      <p className="px-12 py-16 text-text-secondary">
        과목 목록을 불러오지 못했어요. 백엔드가 켜져 있는지 확인해 주세요.
      </p>
    );
  if (banks === null)
    return <p className="px-12 py-16 text-text-secondary">과목을 불러오는 중…</p>;
  if (banks.length === 0)
    return (
      <p className="px-12 py-16 text-text-secondary">
        아직 문제은행이 있는 과목이 없어요. 자료를 올려 파싱이 끝나면 문제은행을 만들 수
        있어요.
      </p>
    );
  return <CourseSelect courses={banks} onSelect={pickCourse} />;
}
