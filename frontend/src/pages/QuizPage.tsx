import { useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { CourseSelect } from "@/pages/quiz/CourseSelect";
import { ScopeSelect } from "@/pages/quiz/ScopeSelect";
import { SolveView, type SolveResult } from "@/pages/quiz/SolveView";
import { ResultView } from "@/pages/quiz/ResultView";
import {
  fetchCourseBanks,
  fetchGenStatus,
  fetchSession,
  requestRefill,
} from "@/pages/quiz/api";
import { loadSolved, recordSolved, solvedCountByToc } from "@/pages/quiz/solved";
import type { CourseBank, QuizStyle, SessionItem } from "@/pages/quiz/mock";

// 문제 페이지 — 확정안 §6. 과목(책) 선택 → 범위 선택 → 풀이 → 결과.
// 문제은행이 코스 단위라 책장처럼 과목부터 고른다.
// 학습 페이지와 데이터를 공유하지 않는다(§7-③): 풀이 결과는 이 페이지 안에서만 산다.
type Step = "course" | "scope" | "solve" | "result";

export function QuizPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const deepCourseId = searchParams.get("course");
  const [step, setStep] = useState<Step>("course");
  const [course, setCourse] = useState<CourseBank | null>(null);
  const [items, setItems] = useState<SessionItem[]>([]);
  const [recycled, setRecycled] = useState(0); // items 뒤쪽 recycled개 = 복습 재등장
  const [results, setResults] = useState<SolveResult[]>([]);
  const [lastScope, setLastScope] = useState<{ tocIndexes: number[]; count: number } | null>(null);
  const [loading, setLoading] = useState(false);
  // 리필(새 문제 만들기) 접수 상태 — 생성은 분 단위라 접수만 하고 화면은
  // 계속 쓴다. 과목을 바꾸면 초기화.
  const [refillState, setRefillState] = useState<"idle" | "requested">("idle");
  // 리필 완료 결과 — saved 수로 "추가됐어요/못 만들었어요"를 가른다.
  // saved: number = done(0이면 빈손), "failed" = 실패. 과목 단위로 기억해
  // 그 과목의 카드·범위·결과 화면에만 보여준다.
  const [refillOutcome, setRefillOutcome] = useState<{
    courseId: string;
    saved: number | "failed";
  } | null>(null);

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

  // 생성·리필 중인 과목이 있으면 5초마다 다시 물어본다 — 책장의 "분석 중"
  // 폴링과 같은 패턴. 끝나면 카드가 "생성 중"→"N문항", 리필 표시→갱신된
  // 문항 수로 저절로 바뀐다. 이 화면에서 리필을 접수한 직후(requested)에도
  // 폴링을 걸어 카드가 진행 상태를 바로 반영하게 한다.
  useEffect(() => {
    const busy =
      banks?.some((b) => b.status === "generating" || b.refilling) ||
      refillState === "requested";
    if (!busy) return;
    const timer = setInterval(() => {
      fetchCourseBanks().then(setBanks).catch(() => {});
    }, 5000);
    return () => clearInterval(timer);
  }, [banks, refillState]);

  const tocTitles = useMemo(
    () =>
      Object.fromEntries(
        (course?.summary?.tocs ?? []).map((t) => [t.toc_index, t.title]),
      ) as Record<number, string>,
    [course],
  );

  // 두 번째 인자(QuizStyle)는 CourseSelect의 mock 시절 계약 잔재 — 기출 여부
  // 표시는 이제 범위 화면의 카드(생성 버튼/기출만 토글)가 전담해서 안 쓴다.
  const pickCourse = (c: CourseBank, _s: QuizStyle) => {
    setCourse(c);
    setRefillState("idle");
    sawRefillRunning.current = false;
    // 다른 과목으로 갈아타면 이전 과목의 리필 결과 안내는 접는다
    if (refillOutcome && refillOutcome.courseId !== c.course_id) setRefillOutcome(null);
    setStep("scope");
  };

  // ?course=<id> 로 들어오면 과목 선택을 건너뛴다 — **책장에서 이미 고른
  // 자료다.** 같은 걸 두 번 고르게 하지 않는다.
  //
  // 한 번만 튄다(`jumped`). 안 그러면 범위 화면에서 "뒤로"를 눌러도 URL이
  // 그대로라 곧장 다시 튕겨서 과목을 못 바꾼다. 그래서 뒤로 갈 때 쿼리도 지운다.
  const jumped = useRef(false);
  useEffect(() => {
    if (jumped.current || !banks || !deepCourseId) return;
    jumped.current = true;
    const found = banks.find((b) => b.course_id === deepCourseId);
    // 못 찾으면 아무것도 안 한다 — 과목 선택 화면이 그대로 뜬다(문제은행이
    // 아직 없는 코스는 `fetchCourseBanks`가 목록에서 빼기 때문에 여기 온다).
    if (found) pickCourse(found, "standard");
    // pickCourse는 매 렌더 새 함수라 deps에 넣으면 루프가 된다. jumped가 가드다.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [banks, deepCourseId]);

  const backToCourses = () => {
    if (deepCourseId) setSearchParams({}, { replace: true });
    setStep("course");
  };

  const start = async (tocIndexes: number[], count: number) => {
    if (!course?.summary) return;
    setLoading(true);
    try {
      // 정답 없는 문항만 도착.
      // 푼 문항 기록(localStorage)을 함께 보내 안 푼 문제를 먼저 받는다.
      const solvedIds = loadSolved(course.course_id, course.summary.document_id)
        .map((e) => e.id);
      const session = await fetchSession(
        course.course_id,
        course.summary.document_id,
        tocIndexes,
        count,
        solvedIds,
      );
      setLastScope({ tocIndexes, count });
      setItems(session.items);
      setRecycled(session.recycled);
      setResults([]);
      setStep("solve");
    } finally {
      setLoading(false);
    }
  };

  // 채점된 문항을 풀이 기록에 남긴다 — 다음 세션의 "안 푼 문제 우선" 재료
  const markSolved = (item: SessionItem) => {
    if (!course?.summary) return;
    recordSolved(course.course_id, course.summary.document_id, item.id, item.toc_index);
  };

  const finish = (r: SolveResult[]) => {
    setResults(r);
    setStep("result");
  };

  // 리필 — AI에게 새 문제 생성을 접수시킨다 (202, 분 단위 백그라운드 작업).
  // 이미 돌고 있으면 서버가 409를 주는데, 사용자 입장에선 "만들고 있어요"와
  // 같은 상태라 requested로 취급한다.
  const refill = async () => {
    if (!course?.summary || refillState === "requested") return;
    setRefillState("requested");
    setRefillOutcome(null); // 새 요청 — 지난 결과 안내는 접는다
    try {
      await requestRefill(course.course_id, course.summary.document_id);
    } catch {
      // 409(이미 생성 중)는 requested 유지가 맞고, 그 외 실패도 재시도 여지를
      // 남기기보다 다음 방문 때 자연스럽게 다시 시도하게 둔다.
    }
  };

  // 선택된 과목의 "지금" 상태 — course는 선택 시점 스냅샷이라, 폴링으로
  // 갱신되는 banks에서 같은 과목을 찾아 리필 진행 여부·문항 수를 실시간으로 본다.
  const liveBank = banks?.find((b) => b.course_id === course?.course_id);
  const liveRefilling = liveBank?.refilling ?? false;

  // 리필이 "돌다가 멈춘" 순간 = 완료 — 접수 상태(requested)를 원복하고,
  // 그 자리에서 결과(saved)를 한 번 조회해 "N개 추가/빈손/실패" 안내 재료로
  // 삼는다. 문항 수 자체는 폴링이 이미 갱신해 준다.
  const sawRefillRunning = useRef(false);
  useEffect(() => {
    if (liveRefilling) {
      sawRefillRunning.current = true;
      return;
    }
    if (!sawRefillRunning.current) return;
    sawRefillRunning.current = false;
    setRefillState("idle");
    if (!course?.summary) return;
    const courseId = course.course_id;
    fetchGenStatus(courseId, course.summary.document_id)
      .then((s) => {
        if (s.status === "done") setRefillOutcome({ courseId, saved: s.saved });
        else if (s.status === "failed") setRefillOutcome({ courseId, saved: "failed" });
        // idle(서버 재시작으로 상태 증발)은 결과를 알 수 없어 안내 생략
      })
      .catch(() => {});
  }, [liveRefilling, course]);

  // 이 범위의 안 푼 문제가 바닥났는가 — 결과 화면의 "새 문제 만들기" 노출 조건.
  // recycled>0(이번 세션에 복습이 섞임) 또는 범위 내 전 문항 풀이 완료.
  const poolLow = (() => {
    if (recycled > 0) return true;
    if (!course?.summary || !lastScope) return false;
    const solvedByToc = solvedCountByToc(
      loadSolved(course.course_id, course.summary.document_id),
    );
    return course.summary.tocs
      .filter((t) => lastScope.tocIndexes.includes(t.toc_index))
      .every((t) => (solvedByToc[t.toc_index] ?? 0) >= t.item_count);
  })();

  if (step === "scope" && course?.summary)
    return (
      <div className={loading ? "pointer-events-none opacity-60" : undefined}>
        <ScopeSelect
          title={course.title}
          summary={liveBank?.summary ?? course.summary}
          solvedByToc={solvedCountByToc(
            loadSolved(course.course_id, course.summary.document_id),
          )}
          refilling={liveRefilling || refillState === "requested"}
          refillOutcome={
            refillOutcome?.courseId === course.course_id ? refillOutcome.saved : null
          }
          onStart={(t, c) => void start(t, c)}
          onBack={backToCourses}
        />
      </div>
    );

  if (step === "solve")
    return (
      <SolveView
        key={items.map((i) => i.id).join(",")}
        items={items}
        recycled={recycled}
        tocTitles={tocTitles}
        onSolved={markSolved}
        onFinish={finish}
      />
    );

  if (step === "result")
    return (
      <ResultView
        results={results}
        tocTitles={tocTitles}
        documentId={course?.summary?.document_id}
        poolLow={poolLow}
        refillState={
          refillState === "requested" || liveRefilling ? "requested" : "idle"
        }
        refillOutcome={
          refillOutcome && refillOutcome.courseId === course?.course_id
            ? refillOutcome.saved
            : null
        }
        onRefill={() => void refill()}
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
  return (
    <CourseSelect courses={banks} refillOutcome={refillOutcome} onSelect={pickCourse} />
  );
}
