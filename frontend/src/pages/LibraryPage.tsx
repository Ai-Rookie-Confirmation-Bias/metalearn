import { Link, useNavigate } from "react-router-dom";
import {
  PlusIcon,
  PlayIcon,
  MagnifyingGlassIcon,
  PencilIcon,
  PenNibIcon,
  BookOpenIcon,
  NotebookIcon,
  GraduationCapIcon,
  BookmarkIcon,
  type Icon,
} from "@phosphor-icons/react";

import { meStats, type CourseSummary } from "@/pages/library/mock";
import { useCreatedCourses } from "@/features/course-create/store";
import { useCourses } from "@/features/library/queries/useCourses";
import { useReviewDue } from "@/features/review/queries/useReviewDue";

// difficulty_est(1~10) → 뱃지 라벨
function difficultyLabel(est: number): string {
  if (est <= 3) return "입문";
  if (est <= 7) return "중급";
  return "고급";
}

// 커버(색+아이콘)는 스키마에 없는 표현 계층 → course.id로 파생.
// 아이콘은 과목 무관 범용 학습 아이콘이라 어느 코스에 붙어도 자연스러움.
// 파랑 계열은 "이어서 학습" 배너(accent)와 겹치지 않게 제외.
type Cover = { grad: string; icon: Icon };
const COVERS: Cover[] = [
  { grad: "from-[#0f172a] to-[#334155]", icon: PencilIcon }, // 남색
  { grad: "from-[#059669] to-[#10b981]", icon: BookOpenIcon }, // 초록
  { grad: "from-[#7c3aed] to-[#a855f7]", icon: PenNibIcon }, // 보라
  { grad: "from-[#d97706] to-[#f59e0b]", icon: NotebookIcon }, // 주황
  { grad: "from-[#e11d48] to-[#fb7185]", icon: GraduationCapIcon }, // 장미
  { grad: "from-[#0d9488] to-[#14b8a6]", icon: BookmarkIcon }, // 청록
];

function hashIndex(id: string) {
  return [...id].reduce((sum, ch) => sum + ch.charCodeAt(0), 0) % COVERS.length;
}

// 각 코스에 커버 배정: 해시로 고른 색을 우선하되, 이미 쓴 색이면 다음 빈 색으로 밀어
// 책장 안에서는 안 겹치게(생일 역설 회피). 코스가 팔레트(6)보다 많아지면 그때부터만 반복.
function assignCovers(list: CourseSummary[]): Map<string, Cover> {
  const used = new Set<number>();
  const map = new Map<string, Cover>();
  for (const c of list) {
    let idx = hashIndex(c.id);
    for (let i = 0; used.has(idx) && i < COVERS.length; i++) {
      idx = (idx + 1) % COVERS.length;
    }
    used.add(idx);
    map.set(c.id, COVERS[idx]);
  }
  return map;
}

// 이어서 학습하기 히어로 — 마지막으로 보던 코스 원클릭 재개(진행 중일 때만)
function ContinueBanner({ course }: { course: CourseSummary }) {
  const progress = Math.round((course.sectionsCompleted / course.sectionsTotal) * 100);

  return (
    <section className="mb-12 flex flex-col gap-6 rounded-2xl bg-accent p-8 text-white sm:flex-row sm:items-center sm:justify-between">
      <div className="min-w-0">
        <span className="inline-block rounded-full bg-white/10 px-3 py-1 text-xs font-semibold text-white/80">
          이어서 학습하기
        </span>
        <h3 className="mt-3 truncate text-2xl font-bold">{course.title}</h3>
        {course.nextSectionTitle && (
          <p className="mt-1 truncate text-sm text-white/60">다음: {course.nextSectionTitle}</p>
        )}
        <div className="mt-4 flex items-center gap-3">
          <div className="h-2 w-48 max-w-full overflow-hidden rounded-full bg-white/25">
            <div className="h-full rounded-full bg-white" style={{ width: `${progress}%` }} />
          </div>
          <span className="text-sm font-semibold text-white/80">{progress}% 완료</span>
        </div>
      </div>

      <Link
        to="/learning"
        className="inline-flex flex-shrink-0 items-center justify-center gap-2 rounded-xl bg-white px-7 py-3.5 text-[0.95rem] font-bold text-accent shadow-sm transition-all hover:-translate-y-0.5 hover:shadow-md"
      >
        <PlayIcon weight="fill" />
        이어서 학습하기
      </Link>
    </section>
  );
}

function BookCard({ course, cover }: { course: CourseSummary; cover: Cover }) {
  const started = course.diagStatus === "completed";
  const progress = course.sectionsTotal
    ? Math.round((course.sectionsCompleted / course.sectionsTotal) * 100)
    : 0;

  // 진단 전이면 진단 시작, 완료+진행0이면 학습 시작, 진행중이면 이어서
  const cta = !started ? "진단 시작하기" : progress > 0 ? "이어서 학습하기" : "학습 시작하기";

  const CoverIcon = cover.icon;

  // 방금 만든 코스 = 씨앗 생성 중 (백엔드에선 gen_status 폴링으로 대체)
  if (course.generating) {
    return (
      <div className="flex min-h-[350px] flex-col overflow-hidden rounded-2xl border border-border-primary bg-white shadow-sm">
        <div
          className={`relative flex h-[140px] items-center justify-center bg-gradient-to-br text-white ${cover.grad}`}
        >
          <span className="h-9 w-9 animate-spin rounded-full border-[3px] border-white/40 border-t-white" />
        </div>
        <div className="flex flex-1 flex-col p-6">
          <h4 className="mb-1 text-[1.125rem] font-bold leading-snug text-text-primary">
            {course.title}
          </h4>
          <p className="mb-6 flex-1 text-[0.9rem] text-text-secondary">
            AI가 커리큘럼을 만들고 있어요…
          </p>
          <div className="mt-auto inline-flex w-full items-center justify-center gap-2 rounded-xl bg-bg-secondary px-5 py-3 text-[0.9rem] font-semibold text-text-tertiary">
            <span className="h-4 w-4 animate-spin rounded-full border-2 border-text-tertiary/40 border-t-text-tertiary" />
            생성 중…
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-[350px] flex-col overflow-hidden rounded-2xl border border-border-primary bg-white shadow-sm transition-all hover:-translate-y-1 hover:border-text-tertiary hover:shadow-lg">
      <div
        className={`relative flex h-[140px] items-center justify-center bg-gradient-to-br text-white ${cover.grad}`}
      >
        <CoverIcon className="text-[3.5rem] opacity-90" />
        <span className="absolute right-4 top-4 rounded-full bg-white/20 px-3 py-1 text-xs font-bold backdrop-blur-sm">
          {difficultyLabel(course.difficultyEst)}
        </span>
      </div>

      <div className="flex flex-1 flex-col p-6">
        <h4 className="mb-1 text-[1.125rem] font-bold leading-snug text-text-primary">
          {course.title}
        </h4>
        <p className="mb-6 flex-1 text-[0.9rem] text-text-secondary">{course.category}</p>

        {/* 진단 완료면 진행률, 진단 전이면 안내 한 줄(바닥 미정이라 진행률 없음) */}
        {started ? (
          <div className="mb-4">
            <div className="mb-2 flex justify-between text-[0.85rem] font-semibold">
              <span className="text-text-secondary">진행률</span>
              <span className="text-primary">{progress}%</span>
            </div>
            <div className="h-2 w-full overflow-hidden rounded-full bg-bg-secondary">
              <div
                className="h-full rounded-full bg-accent transition-all"
                style={{ width: `${progress}%` }}
              />
            </div>
          </div>
        ) : (
          <div className="mb-4 flex items-center gap-1.5 text-[0.85rem] text-text-tertiary">
            <MagnifyingGlassIcon className="text-base" />
            학습 전 수준 진단이 필요해요
          </div>
        )}

        {/* 진단 전이면 /diagnosis/:courseId, 진단 후엔 학습 화면으로 */}
        <Link
          to={started ? "/learning" : `/diagnosis/${course.id}`}
          className="mt-auto inline-flex w-full items-center justify-center rounded-xl bg-primary px-5 py-3 text-[0.9rem] font-semibold text-white shadow-sm transition-all hover:bg-primary-hover hover:-translate-y-0.5 hover:shadow-md"
        >
          {cta}
        </Link>
      </div>
    </div>
  );
}

export function LibraryPage() {
  const navigate = useNavigate();
  const drafts = useCreatedCourses((s) => s.drafts);

  // 서버 책장(GET /api/courses) — mock 대체. 로딩 중엔 빈 배열.
  const { data: serverCourses = [] } = useCourses();
  // 복습 도래(GET /api/review/due) — 망각곡선 도래 개념 수
  const { data: reviewDue } = useReviewDue();

  // 방금 만든 코스(스토어)를 CourseSummary 모양으로 → 서버 목록과 합쳐 렌더.
  const draftCourses: CourseSummary[] = drafts.map((d) => ({
    id: d.id,
    title: d.title,
    category: null,
    difficultyEst: 5,
    diagStatus: "not_started",
    sectionsTotal: 0,
    sectionsCompleted: 0,
    lastActivityAt: null,
    generating: d.generating,
  }));
  const allCourses = [...draftCourses, ...serverCourses];

  // 이어서 학습할 코스 = 진행 중(진단 완료 & 0<진행<100) 코스 중 마지막 학습이 가장 최근인 것.
  // 정렬은 프론트에서 lastActivityAt(서버가 MAX(attempts.created_at)로 계산해 준 값) 최신순으로.
  const continueCourse = allCourses
    .filter(
      (c) =>
        c.diagStatus === "completed" &&
        c.sectionsCompleted > 0 &&
        c.sectionsCompleted < c.sectionsTotal,
    )
    .sort((a, b) => (b.lastActivityAt ?? "").localeCompare(a.lastActivityAt ?? ""))[0];

  // 커버 색/아이콘을 책장 안에서 안 겹치게 미리 배정
  const coverByCourse = assignCovers(allCourses);

  return (
    <div className="mx-auto w-full max-w-[1400px] px-12 py-12">
      <div className="mb-10">
        <h2 className="mb-1 text-[2rem] font-extrabold tracking-tight text-text-primary">
          오늘도 성장할 준비 되셨나요?
        </h2>
        <p className="text-text-secondary">
          {meStats.streakDays > 0
            ? `지금까지 ${meStats.streakDays}일째 꾸준히 학습 중입니다.`
            : "학습을 시작해볼까요?"}
        </p>
      </div>

      {reviewDue && reviewDue.dueCount > 0 && (
        <div className="mb-6 flex items-center justify-between gap-4 rounded-2xl border border-accent/30 bg-accent/[0.06] px-6 py-4">
          <div className="text-[0.95rem] text-text-primary">
            🔁 복습할 때가 된 개념이 <b className="text-accent">{reviewDue.dueCount}개</b> 있어요.
            지금 다시 꺼내보면 오래 기억돼요.
          </div>
          <Link
            to="/review"
            className="shrink-0 rounded-xl bg-accent px-4 py-2 text-[0.85rem] font-semibold text-white transition-transform hover:-translate-y-0.5"
          >
            복습하러 가기
          </Link>
        </div>
      )}

      {continueCourse && <ContinueBanner course={continueCourse} />}

      {/* 나의 책장 */}
      <section>
        <div className="mb-6 flex items-end justify-between">
          <h3 className="text-xl font-bold text-text-primary">나의 책장</h3>
        </div>

        {allCourses.length === 0 ? (
          /* 첫 사용자(코스 0개) — 새 학습 시작을 크게 강조한 빈 상태 */
          <button
            type="button"
            onClick={() => navigate("/create")}
            className="group flex w-full flex-col items-center justify-center rounded-2xl border-2 border-dashed border-accent/40 bg-accent/5 py-20 text-center transition-colors hover:bg-accent/10"
          >
            <div className="mb-6 flex h-20 w-20 items-center justify-center rounded-full bg-accent text-[2.5rem] text-white shadow-sm">
              <PlusIcon />
            </div>
            <h4 className="text-xl font-bold text-text-primary">첫 학습을 시작해보세요</h4>
            <p className="mt-1.5 text-text-secondary">
              자료를 올리면 AI가 나만의 커리큘럼을 만들어드려요.
            </p>
            <span className="mt-6 inline-flex items-center gap-2 rounded-xl bg-accent px-7 py-3 text-[0.95rem] font-semibold text-white shadow-sm transition-transform group-hover:-translate-y-0.5">
              새로운 학습 시작하기
            </span>
          </button>
        ) : (
          <div className="grid grid-cols-[repeat(auto-fill,minmax(300px,1fr))] gap-8">
            {/* 새 학습 추가 슬롯 — 맨 앞 고정(코스 많아도 좌상단에서 바로 찾음) */}
            <button
              type="button"
              onClick={() => navigate("/create")}
              className="group flex min-h-[350px] flex-col items-center justify-center rounded-2xl border-2 border-dashed border-border-primary p-8 text-center transition-colors hover:border-accent hover:bg-accent/5"
            >
              <div className="mb-5 flex h-16 w-16 items-center justify-center rounded-full bg-bg-secondary text-[2rem] text-text-tertiary transition-colors group-hover:bg-accent group-hover:text-white">
                <PlusIcon />
              </div>
              <h4 className="mb-1 text-[1.125rem] font-bold text-text-primary">새로운 학습 시작하기</h4>
              <p className="text-[0.9rem] text-text-secondary">새로운 목표를 책장에 꽂아보세요.</p>
            </button>

            {allCourses.map((course) => (
              <BookCard key={course.id} course={course} cover={coverByCourse.get(course.id)!} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
