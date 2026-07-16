import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { clsx } from "clsx";
import {
  ArrowLeftIcon,
  ArrowRightIcon,
  ArrowsOutSimpleIcon,
  LockKeyIcon,
  CheckCircleIcon,
  ListIcon,
  RobotIcon,
  SparkleIcon,
  XIcon,
} from "@phosphor-icons/react";
import { useQueryClient } from "@tanstack/react-query";

import { BlockRenderer } from "@/features/learning/blocks/registry";
import type { AnswerEvent, AttemptResult, OnAnswer } from "@/features/learning/blocks/types";
import type { AttemptResponse } from "@/features/learning/api/submitAttempt";
import {
  getSupplement,
  type SupplementResponse,
} from "@/features/learning/api/getSupplement";
import { CurriculumPanel } from "@/pages/learning/CurriculumPanel";
import { AiTutorPanel } from "@/pages/learning/AiTutorPanel";
import type { Chapter as PanelChapter } from "@/pages/learning/mock";
import { useCourses } from "@/features/library/queries/useCourses";
import { useCourseTree } from "@/features/learning/queries/useCourseTree";
import { useSectionBlocks } from "@/features/learning/queries/useSectionBlocks";
import { useSubmitAttempt } from "@/features/learning/queries/useSubmitAttempt";
import { useGenerateChapter } from "@/features/learning/queries/useGenerateChapter";
import { generateChapter } from "@/features/learning/api/generateChapter";
import { useReadComplete } from "@/features/learning/queries/useReadComplete";

// 학습 화면 — 3컬럼(커리큘럼 / 블록 / AI튜터). 데이터는 전부 백엔드:
//   트리 = GET /courses/:id · 절 블록 = GET /sections/:id(지연) · 채점 = POST /attempts(라운드트립).
export function LearningPage() {
  const queryClient = useQueryClient();
  const { courseId: courseIdParam } = useParams<{ courseId: string }>();
  const { data: courses } = useCourses();
  // URL의 :courseId 우선 — 책장에서 클릭한 코스로 진입. 없으면 첫 코스(하위호환).
  const courseId = courseIdParam ?? courses?.[0]?.id;
  const category = courses?.find((c) => c.id === courseId)?.category ?? "";
  const { data: tree, isLoading: treeLoading } = useCourseTree(courseId);

  const chapters = useMemo(() => tree?.chapters ?? [], [tree]);
  const flatSections = useMemo(() => chapters.flatMap((c) => c.sections), [chapters]);

  // 휘발성 UI(현재 보고 있는 절)만 클라 상태. 진행/완료/잠금은 전부 서버(트리) 미러.
  const [currentSectionId, setCurrentSectionId] = useState<string | null>(null);
  // 몰입 뷰어 — 좌(커리큘럼) 패널을 숨기고 본문에만 집중.
  const [immersive, setImmersive] = useState(false);
  // AI 튜터 — 기본은 닫힘(FAB). 학습이 주인공, 튜터는 필요할 때만(정답 자판기 방지).
  const [tutorOpen, setTutorOpen] = useState(false);
  const [tutorUnread, setTutorUnread] = useState(false);
  // 살아있는 커리큘럼 신호(서버 attempt 응답) — 원인 국소화·선행 삽입·복귀 표면화
  const [signal, setSignal] = useState<AttemptResponse | null>(null);
  // 오답 맞춤 보충(재설명) — nextAction=supplement 시 자동 요청, AI튜터 패널에 표시
  const [supplement, setSupplement] = useState<
    | { status: "idle" }
    | { status: "loading" }
    | { status: "ready"; data: SupplementResponse }
  >({ status: "idle" });

  // 코스 전환 시(같은 라우트 요소라 remount 없음) 이전 코스의 절 선택·신호 리셋
  useEffect(() => {
    setCurrentSectionId(null);
    setSignal(null);
    setSupplement({ status: "idle" });
  }, [courseId]);

  // 오답 재설명이 도착했는데 패널이 닫혀 있으면 FAB에 알림 점 — 말없이 사라지지 않게
  useEffect(() => {
    if (supplement.status !== "idle" && !tutorOpen) setTutorUnread(true);
  }, [supplement.status, tutorOpen]);

  // 시작 절 초기화 — ?section=(지식 지도 딥링크)이 있으면 그 절, 없으면 첫 미완료.
  const [searchParams] = useSearchParams();
  const sectionParam = searchParams.get("section");
  useEffect(() => {
    if (!tree) return;
    const secs = tree.chapters.flatMap((c) => c.sections);
    setCurrentSectionId(
      (cur) =>
        cur ??
        (sectionParam && secs.some((s) => s.id === sectionParam) ? sectionParam : null) ??
        secs.find((s) => s.progressStatus !== "completed")?.id ??
        secs[0]?.id ??
        null,
    );
  }, [tree, sectionParam]);

  const { data: sectionData, isLoading: blocksLoading } = useSectionBlocks(
    currentSectionId ?? undefined,
  );
  const blocks = sectionData?.blocks ?? [];

  const submit = useSubmitAttempt();
  const generate = useGenerateChapter();
  const readComplete = useReadComplete();

  // 라운드트립 채점 — userInput만 보내고 서버가 correct/reveal + 완료/숙련도까지 판정.
  // 프론트는 판단하지 않는다: 채점 후 트리를 refetch해 진행/완료/잠금을 서버에서 다시 읽는다.
  const onAnswer: OnAnswer = async (e: AnswerEvent): Promise<AttemptResult> => {
    const r = await submit.mutateAsync(e);
    queryClient.invalidateQueries({ queryKey: ["courseTree"] });
    setSignal(r); // 원인 국소화/선행 삽입/복귀 신호 표면화
    // 오답 + supplement 신호 → 맞춤 재설명 자동 요청(개입 사다리 ②).
    // reveal(정답·해설)은 위 응답으로 즉시 뜨고, 재설명은 수 초 뒤 튜터 패널에 도착.
    // cause=misconception도 포함 — 오개념의 처방은 선행 삽입이 아니라 재설명 지속
    // (서버도 이 경우 선행 삽입을 억제한다).
    const wrong =
      r.correct === false || (typeof r.score === "number" && r.score < 0.6);
    const wantsSupplement =
      r.nextAction?.action === "supplement" || r.cause?.type === "misconception";
    if (wrong && wantsSupplement && e.blockId) {
      setSupplement({ status: "loading" });
      getSupplement(e.blockId)
        .then((s) => setSupplement({ status: "ready", data: s }))
        .catch(() => setSupplement({ status: "idle" }));
    } else {
      setSupplement({ status: "idle" });
    }
    return r;
  };

  // 살아있는 커리큘럼: 서버가 선행 삽입/복귀를 알려주면 해당 절로 이동
  const goToSection = (sectionId: string) => {
    setSignal(null);
    setSupplement({ status: "idle" });
    setCurrentSectionId(sectionId);
  };

  // ── 파생(전부 서버 트리에서) ──
  const currentChapter = chapters.find((c) =>
    c.sections.some((s) => s.id === currentSectionId),
  );
  const currentSection = flatSections.find((s) => s.id === currentSectionId);
  const currentIndex = flatSections.findIndex((s) => s.id === currentSectionId);
  const nextSection = flatSections[currentIndex + 1];

  // 다음 강의 프리페치(UX): 현재 챕터에 들어서는 순간, 다음 챕터가 아직 생성
  // 전(pending)이면 백그라운드로 미리 생성 트리거 → 넘어갈 때 '생성 중' 없이
  // 바로 뜬다(생성 ~1~2분이라 리드타임 확보 위해 절이 아니라 챕터 단위로 앞서
  // 생성). 생성 API는 멱등이라 중복 호출 무해. 챕터당 1회만 시도.
  const prefetchedRef = useRef<Set<string>>(new Set());
  useEffect(() => {
    if (!currentChapter) return;
    const idx = chapters.findIndex((c) => c.id === currentChapter.id);
    const nextChapter = chapters[idx + 1];
    if (!nextChapter || nextChapter.genStatus !== "pending") return;
    if (prefetchedRef.current.has(nextChapter.id)) return;
    prefetchedRef.current.add(nextChapter.id);
    generateChapter(nextChapter.id)
      .then(() => queryClient.invalidateQueries({ queryKey: ["courseTree"] }))
      .catch(() => prefetchedRef.current.delete(nextChapter.id));
  }, [currentChapter, chapters, queryClient]);

  // 자동 생성: 현재 챕터가 pending이면 버튼 없이 즉시 트리거(챕터당 1회, API 멱등).
  // 사용자는 '생성하기'를 누를 필요가 없다 — 들어오면 만들어지기 시작한다.
  useEffect(() => {
    if (!currentChapter || currentChapter.genStatus !== "pending") return;
    if (prefetchedRef.current.has(currentChapter.id)) return;
    prefetchedRef.current.add(currentChapter.id);
    generateChapter(currentChapter.id)
      .then(() => queryClient.invalidateQueries({ queryKey: ["courseTree"] }))
      .catch(() => prefetchedRef.current.delete(currentChapter.id));
  }, [currentChapter, queryClient]);

  // 자동 새로고침: 생성이 도는 동안(pending/generating + 블록 없음) 5초 간격
  // 폴링 — ready로 바뀌고 블록이 생기면 화면이 스스로 갱신된다(수동 새로고침 불필요).
  const waitingGeneration =
    blocks.length === 0 &&
    !blocksLoading &&
    (currentChapter?.genStatus === "pending" ||
      currentChapter?.genStatus === "generating");
  useEffect(() => {
    if (!waitingGeneration) return;
    const timer = setInterval(() => {
      queryClient.invalidateQueries({ queryKey: ["courseTree"] });
      queryClient.invalidateQueries({ queryKey: ["sectionBlocks", currentSectionId] });
    }, 5000);
    return () => clearInterval(timer);
  }, [waitingGeneration, currentSectionId, queryClient]);

  // 완료/잠금 = 서버 진실(section_progress → tree.progressStatus)의 미러. 클라 계산 아님.
  const completedIds = useMemo(
    () =>
      new Set(
        flatSections.filter((s) => s.progressStatus === "completed").map((s) => s.id),
      ),
    [flatSections],
  );
  // 잠금은 서버가 계산(tree.locked) → 프론트는 미러만(순차 규칙 판단 안 함)
  const unlockedIds = useMemo(
    () => new Set(flatSections.filter((s) => !s.locked).map((s) => s.id)),
    [flatSections],
  );

  // 다음으로 진행 가능 = 이 절이 서버에서 완료 처리됨(= tracked 전부 통과). 백엔드가 판정.
  const unlocked = currentSection?.progressStatus === "completed";
  // 열람 전용 절 = 봉투에 tracked 블록이 하나도 없음(예: analogy만 있는 선행 절).
  // 인출로는 완료가 불가능하므로 '다 읽었어요' 게이트를 노출한다(완료 판정은 서버).
  const hasTracked = blocks.some((b) => b.tracked);

  // CurriculumPanel용 chapters(패널은 블록을 안 쓰므로 빈 배열)
  // 선행 장(origin=prereq)이 준비시키는 본편 = 그 뒤에 오는 첫 book 장.
  const panelChapters: PanelChapter[] = chapters.map((c, i) => ({
    id: c.id,
    title: c.title,
    origin: c.origin as "book" | "prereq" | undefined,
    prereqForTitle:
      c.origin === "prereq"
        ? chapters.slice(i + 1).find((x) => x.origin === "book")?.title
        : undefined,
    reason: c.reason, // 이유 라벨(서버) — 왜 이 장이 끼워졌는지
    sections: c.sections.map((s) => ({ id: s.id, title: s.title, blocks: [] })),
  }));

  // 현재 절이 선행 장에 속하면, 어느 본편을 위한 선행인지(배너용)
  const currentPrereqFor =
    currentChapter?.origin === "prereq"
      ? chapters
          .slice(chapters.findIndex((c) => c.id === currentChapter.id) + 1)
          .find((x) => x.origin === "book")?.title
      : undefined;

  const goNext = () => {
    // 완료 판정은 서버(section_progress)가 이미 처리 → 프론트는 다음 절로 이동만.
    if (nextSection) setCurrentSectionId(nextSection.id);
  };

  // 열람 전용 절의 '다 읽었어요' — 서버가 완료 판정+커서 복귀 pop까지 처리(라운드트립).
  // 이후 이동은 기존 완료 흐름과 동일: 복귀 지점이 있으면 원래 절로, 없으면 다음 절로.
  const onReadComplete = async () => {
    if (!currentSectionId) return;
    const r = await readComplete.mutateAsync(currentSectionId);
    if (r.resumeSectionId) {
      goToSection(r.resumeSectionId);
    } else {
      goNext();
    }
  };

  const onGenerate = async () => {
    if (!currentChapter) return;
    await generate.mutateAsync(currentChapter.id);
  };

  if (treeLoading || !tree) {
    return (
      <div className="grid h-screen place-items-center text-text-tertiary">코스 불러오는 중…</div>
    );
  }

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-[#f3f4f6]">
      {/* 상단 학습 헤더 */}
      <header className="z-20 flex h-16 flex-shrink-0 items-center justify-between border-b border-border-primary bg-white px-6">
        <div className="flex items-center gap-6">
          <Link
            to="/library"
            className="flex items-center gap-2 text-[0.9rem] font-semibold text-text-secondary transition-colors hover:text-primary"
          >
            <ArrowLeftIcon /> 책장으로
          </Link>
          <div className="flex items-center gap-4 border-l border-border-primary pl-6">
            {category && (
              <span className="rounded-md bg-bg-secondary px-2.5 py-1 text-xs font-bold text-text-secondary">
                {category}
              </span>
            )}
            <h1 className="text-[1.1rem] font-bold text-primary">{tree.title}</h1>
          </div>
        </div>
        <div className="flex items-center gap-4">
          <button
            type="button"
            onClick={() => setImmersive((v) => !v)}
            aria-pressed={immersive}
            className={clsx(
              "flex items-center gap-2 rounded-xl border px-4 py-2 text-[0.85rem] font-semibold transition-colors",
              immersive
                ? "border-primary bg-primary text-white hover:bg-primary-hover"
                : "border-border-primary bg-bg-secondary text-text-primary hover:bg-border-primary/50",
            )}
          >
            <ArrowsOutSimpleIcon weight="fill" />{" "}
            {immersive ? "몰입 뷰어 끄기" : "몰입 뷰어 켜기"}
          </button>
          <button
            type="button"
            className="flex h-10 w-10 items-center justify-center rounded-full bg-bg-secondary text-xl text-text-secondary"
          >
            <ListIcon />
          </button>
        </div>
      </header>

      {/* 3컬럼 (몰입 뷰어 켜면 좌우 패널 숨김) */}
      <div className="flex flex-1 overflow-hidden">
        {!immersive && (
          <CurriculumPanel
            chapters={panelChapters}
            currentSectionId={currentSectionId ?? ""}
            completedIds={completedIds}
            unlockedIds={unlockedIds}
            onSelect={setCurrentSectionId}
          />
        )}

        {/* 중앙: 현재 절의 블록 렌더 */}
        <main className="flex-1 overflow-y-auto bg-white" key={currentSectionId}>
          <div className="mx-auto w-full max-w-[1000px] p-12">
            <h2 className="mb-6 text-[2rem] font-extrabold tracking-tight text-text-primary">
              {currentSection?.title ?? ""}
            </h2>

            {/* 선행 장 진입 안내 — 지금 학습 중인 절이 선행학습이면 명시적으로 알림 */}
            {currentChapter?.origin === "prereq" && (
              <div className="mb-6 flex items-start gap-3 rounded-2xl border border-[#f59e0b]/40 bg-[#f59e0b]/10 px-5 py-4">
                <span className="mt-0.5 shrink-0 rounded-md bg-[#f59e0b] px-2 py-1 text-[0.72rem] font-bold text-white">
                  선행 학습
                </span>
                <div className="text-[0.9rem] leading-relaxed text-[#b45309]">
                  <b>기초를 먼저 다지는 선행 학습이에요.</b>{" "}
                  {/* 이유 라벨(서버 우선) — 커리큘럼은 말없이 변하지 않는다 */}
                  {currentChapter?.reason ? (
                    currentChapter.reason
                  ) : currentPrereqFor ? (
                    <>
                      다음 본편 <b>"{currentPrereqFor}"</b>을(를) 배우기 전에 필요한 선수
                      개념이라, 여기서 먼저 익히고 넘어가요.
                    </>
                  ) : (
                    "본 강의 전에 필요한 선수 개념이라 먼저 익히고 넘어가요."
                  )}
                </div>
              </div>
            )}

            {/* 살아있는 커리큘럼 — 서버가 선수결손 감지 시 선행 절 삽입 후 이동 유도 */}
            {signal?.prerequisite && (
              <div className="mb-6 flex items-center justify-between gap-4 rounded-2xl border border-[#f59e0b]/40 bg-[#f59e0b]/10 px-5 py-4">
                <div className="text-[0.9rem] text-[#b45309]">
                  <b>선수 개념 결손이 감지됐어요.</b> "{signal.prerequisite.title}"을(를) 먼저 다지면
                  이 개념이 훨씬 쉬워져요.
                </div>
                <button
                  type="button"
                  onClick={() => goToSection(signal.prerequisite!.sectionId)}
                  className="shrink-0 rounded-xl bg-[#b45309] px-4 py-2 text-[0.85rem] font-semibold text-white"
                >
                  선행 먼저 학습
                </button>
              </div>
            )}
            {signal?.resumeSectionId && (
              <div className="mb-6 flex items-center justify-between gap-4 rounded-2xl border border-[#10b981]/40 bg-[#10b981]/10 px-5 py-4">
                <div className="text-[0.9rem] text-[#047857]">
                  <b>선행 학습을 마쳤어요.</b> 원래 배우던 절로 돌아갈까요?
                </div>
                <button
                  type="button"
                  onClick={() => goToSection(signal.resumeSectionId!)}
                  className="shrink-0 rounded-xl bg-[#047857] px-4 py-2 text-[0.85rem] font-semibold text-white"
                >
                  원래 절로 복귀
                </button>
              </div>
            )}

            {blocksLoading ? (
              <div className="py-16 text-center text-text-tertiary">불러오는 중…</div>
            ) : blocks.length === 0 ? (
              // 아직 생성 안 된 절 — 자동으로 생성 트리거·폴링되므로 버튼 없이
              // 진행 안내만 보여준다. 실패했을 때만 '다시 시도'를 노출한다.
              currentChapter?.genStatus === "failed" ? (
                <div className="flex flex-col items-center gap-4 rounded-2xl border-2 border-dashed border-red-200 bg-red-50/40 p-12 text-center">
                  <SparkleIcon className="text-3xl text-red-400" weight="fill" />
                  <p className="font-semibold text-text-secondary">
                    콘텐츠 생성에 실패했어요. 다시 시도해주세요.
                  </p>
                  <button
                    type="button"
                    onClick={onGenerate}
                    disabled={generate.isPending}
                    className="rounded-xl bg-primary px-5 py-[0.6rem] text-[0.9rem] font-semibold text-white shadow-sm transition-all hover:-translate-y-0.5 hover:bg-primary-hover disabled:opacity-50"
                  >
                    {generate.isPending ? "다시 생성 중…" : "다시 생성하기"}
                  </button>
                </div>
              ) : (
                <div className="flex flex-col items-center gap-4 rounded-2xl border-2 border-dashed border-border-primary bg-bg-secondary/40 p-12 text-center">
                  <span className="h-8 w-8 animate-spin rounded-full border-2 border-primary/30 border-t-primary" />
                  <p className="font-semibold text-text-secondary">
                    AI가 이 챕터의 학습 콘텐츠를 만들고 있어요
                  </p>
                  <p className="text-[0.9rem] text-text-tertiary">
                    보통 1~2분 걸려요. 완성되면 자동으로 열려요 — 기다리기만 하면 돼요.
                  </p>
                </div>
              )
            ) : (
              blocks.map((block) => (
                <BlockRenderer
                  key={`${currentSectionId}-${block.id}`}
                  block={block}
                  onAnswer={onAnswer}
                />
              ))
            )}

            {/* 열람 전용 게이트 — tracked 0개 절은 인출로 완료가 불가 → '다 읽었어요'로 완료 */}
            {blocks.length > 0 && !hasTracked && !unlocked && (
              <div className="mt-12 flex flex-col items-center gap-4 border-t border-border-primary pt-8">
                <div className="flex items-center gap-1.5 text-[0.9rem] font-medium text-text-tertiary">
                  <CheckCircleIcon weight="fill" className="text-[#10b981]" /> 이 절은 인출 문제
                  없이 읽기만으로 완료할 수 있습니다.
                </div>
                <button
                  type="button"
                  onClick={onReadComplete}
                  disabled={readComplete.isPending}
                  className={clsx(
                    "inline-flex items-center gap-2 rounded-xl px-5 py-[0.6rem] text-[13.3333px] font-semibold leading-[normal] text-white shadow-sm transition-all",
                    readComplete.isPending
                      ? "cursor-not-allowed bg-text-tertiary opacity-70"
                      : "bg-primary hover:-translate-y-0.5 hover:bg-primary-hover hover:shadow-md",
                  )}
                >
                  {readComplete.isPending ? "완료 처리 중…" : "다 읽었어요 · 계속하기"}{" "}
                  <ArrowRightIcon />
                </button>
              </div>
            )}

            {/* 잠금 게이트 — tracked 전부 통과해야 다음 */}
            {blocks.length > 0 && (hasTracked || unlocked) && (
              <div className="mt-12 flex flex-col items-center gap-4 border-t border-border-primary pt-8">
                {unlocked ? (
                  <div className="flex items-center gap-1.5 text-[0.9rem] font-medium text-text-tertiary">
                    <CheckCircleIcon weight="fill" className="text-[#10b981]" /> 모든 인출을
                    완료했습니다. 다음으로 넘어갈 수 있습니다.
                  </div>
                ) : (
                  <div className="flex items-center gap-1.5 text-[0.9rem] font-medium text-text-tertiary">
                    <LockKeyIcon weight="fill" /> 위의 모든 인출 문제에 답해야 진행할 수 있습니다.
                  </div>
                )}
                <button
                  type="button"
                  onClick={goNext}
                  disabled={!unlocked}
                  className={clsx(
                    "inline-flex items-center gap-2 rounded-xl px-5 py-[0.6rem] text-[13.3333px] font-semibold leading-[normal] text-white shadow-sm transition-all",
                    unlocked
                      ? "bg-primary hover:-translate-y-0.5 hover:bg-primary-hover hover:shadow-md"
                      : "cursor-not-allowed bg-text-tertiary opacity-70",
                  )}
                >
                  {nextSection ? "다음 강의로 넘어가기" : "코스 완료하기"} <ArrowRightIcon />
                </button>
              </div>
            )}
          </div>
        </main>

      </div>

      {/* AI 튜터 — 우측 하단 FAB + 플로팅 패널. 항상 떠 있지 않는다:
          학습 칸을 넓게 쓰고, 튜터 의존(정답 자판기화)을 구조적으로 줄인다. */}
      {tutorOpen && (
        <div className="fixed bottom-24 right-6 z-50 flex h-[min(620px,calc(100vh-130px))] w-[380px] max-w-[calc(100vw-3rem)] flex-col overflow-hidden rounded-2xl border border-border-primary bg-white shadow-2xl">
          <AiTutorPanel
            sectionId={currentSectionId}
            signal={signal}
            supplement={supplement}
            onClose={() => setTutorOpen(false)}
          />
        </div>
      )}
      <button
        type="button"
        onClick={() => {
          setTutorOpen((o) => !o);
          setTutorUnread(false);
        }}
        aria-label={tutorOpen ? "AI 튜터 닫기" : "AI 튜터 열기"}
        className="fixed bottom-6 right-6 z-50 flex h-14 w-14 items-center justify-center rounded-full bg-accent text-2xl text-white shadow-lg transition-transform hover:scale-105"
      >
        {tutorOpen ? <XIcon weight="bold" /> : <RobotIcon weight="fill" />}
        {!tutorOpen && tutorUnread && (
          <span className="absolute -right-0.5 -top-0.5 h-3.5 w-3.5 animate-pulse rounded-full border-2 border-white bg-[#ef4444]" />
        )}
      </button>
    </div>
  );
}
