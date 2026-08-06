import { clsx } from "clsx";
import {
  PencilIcon,
  BookOpenIcon,
  PenNibIcon,
  NotebookIcon,
  GraduationCapIcon,
  BookmarkIcon,
  ExamIcon,
  PlayIcon,
  type Icon,
} from "@phosphor-icons/react";

import type { CourseBank, QuizStyle } from "./mock";

// 화면 0: 과목(책) 선택 — 책장(LibraryPage)과 같은 책 카드 문법.
// 문제은행은 코스 단위(course_id)로 생성되므로 이 선택이 모든 API 호출의 전제.

// 커버 팔레트 — LibraryPage와 동일 (같은 코스가 양쪽에서 같은 색이 되도록 해시도 동일)
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

function assignCovers(list: CourseBank[]): Map<string, Cover> {
  const used = new Set<number>();
  const map = new Map<string, Cover>();
  for (const c of list) {
    let idx = hashIndex(c.course_id);
    for (let i = 0; used.has(idx) && i < COVERS.length; i++) {
      idx = (idx + 1) % COVERS.length;
    }
    used.add(idx);
    map.set(c.course_id, COVERS[idx]);
  }
  return map;
}

// 최근 학습한 과목 추천 — 책장 ContinueBanner와 같은 문법.
// 학습 기록은 "어디를 풀지" 안내에만 쓰인다 (문항 선정에는 불사용 — §7-③의 선).
function RecentStudyBanner({
  course,
  onSelect,
}: {
  course: CourseBank;
  onSelect: (course: CourseBank, style: QuizStyle) => void;
}) {
  return (
    <section className="mb-12 flex flex-col gap-6 rounded-2xl bg-accent p-8 text-white sm:flex-row sm:items-center sm:justify-between">
      <div className="min-w-0">
        <span className="inline-block rounded-full bg-white/10 px-3 py-1 text-xs font-semibold text-white/80">
          최근 학습한 과목
        </span>
        <h3 className="mt-3 truncate text-2xl font-bold">{course.title}</h3>
        <p className="mt-1 text-sm text-white/60">
          배운 내용이 진짜 꺼내지는지 문제로 확인해보세요.
        </p>
      </div>

      <button
        type="button"
        onClick={() => onSelect(course, "standard")}
        className="inline-flex flex-shrink-0 items-center justify-center gap-2 rounded-xl bg-white px-7 py-3.5 text-[0.95rem] font-bold text-accent shadow-sm transition-all hover:-translate-y-0.5 hover:shadow-md"
      >
        <PlayIcon weight="fill" />
        이 과목 문제 풀기
      </button>
    </section>
  );
}

function QuizBookCard({
  course,
  cover,
  onSelect,
}: {
  course: CourseBank;
  cover: Cover;
  onSelect: (course: CourseBank, style: QuizStyle) => void;
}) {
  const CoverIcon = cover.icon;

  // 문제은행 배치가 도는 중 (백엔드에선 gen_status 폴링으로 대체) — BookCard.generating과 동일 문법
  if (course.status === "generating") {
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
            교재에서 문제를 만들고 있어요…
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
          {course.summary?.total}문항
        </span>
      </div>

      <div className="flex flex-1 flex-col p-6">
        <h4 className="mb-1 text-[1.125rem] font-bold leading-snug text-text-primary">
          {course.title}
        </h4>
        <p className="mb-6 flex-1 text-[0.9rem] text-text-secondary">{course.category}</p>

        <div className="mb-4 flex items-center gap-1.5 text-[0.85rem] text-text-tertiary">
          <ExamIcon className="text-base" />
          목차 {course.summary?.tocs.length}개 · 범위를 골라 풀 수 있어요
        </div>

        {/* 기출(kind=exam)을 올린 과목만 기출 스타일 모드가 존재 */}
        {course.has_exam_style ? (
          <div className="mt-auto flex flex-col gap-2">
            <button
              type="button"
              onClick={() => onSelect(course, "standard")}
              className="inline-flex w-full items-center justify-center rounded-xl bg-primary px-5 py-3 text-[0.9rem] font-semibold text-white shadow-sm transition-all hover:-translate-y-0.5 hover:bg-primary-hover hover:shadow-md"
            >
              일반 문제 풀기
            </button>
            <button
              type="button"
              onClick={() => onSelect(course, "exam")}
              className="inline-flex w-full items-center justify-center gap-1.5 rounded-xl border border-accent bg-accent/5 px-5 py-3 text-[0.9rem] font-semibold text-accent transition-all hover:-translate-y-0.5 hover:bg-accent/10"
            >
              <ExamIcon weight="fill" /> 기출 스타일로 풀기
            </button>
          </div>
        ) : (
          <button
            type="button"
            onClick={() => onSelect(course, "standard")}
            className="mt-auto inline-flex w-full items-center justify-center rounded-xl bg-primary px-5 py-3 text-[0.9rem] font-semibold text-white shadow-sm transition-all hover:-translate-y-0.5 hover:bg-primary-hover hover:shadow-md"
          >
            문제 풀러 가기
          </button>
        )}
      </div>
    </div>
  );
}

export function CourseSelect({
  courses,
  onSelect,
}: {
  courses: CourseBank[];
  onSelect: (course: CourseBank, style: QuizStyle) => void;
}) {
  const coverByCourse = assignCovers(courses);

  // 추천 = 문제은행이 준비된 과목 중 마지막 학습이 가장 최근인 것 (책장과 같은 기준)
  const recent = courses
    .filter((c) => c.status === "ready" && c.last_activity_at)
    .sort((a, b) => (b.last_activity_at ?? "").localeCompare(a.last_activity_at ?? ""))[0];

  return (
    <div className="mx-auto w-full max-w-[1400px] px-12 py-12">
      <div className="mb-10">
        <h2 className="mb-1 text-[2rem] font-extrabold tracking-tight text-text-primary">
          문제집
        </h2>
        <p className="text-text-secondary">
          어떤 과목의 문제를 풀까요? 모든 문제는 올린 교재의 원문에서 만들어졌어요.
        </p>
      </div>

      {recent && <RecentStudyBanner course={recent} onSelect={onSelect} />}

      <section>
        <div className={clsx("grid gap-8", "grid-cols-[repeat(auto-fill,minmax(300px,1fr))]")}>
          {courses.map((course) => (
            <QuizBookCard
              key={course.course_id}
              course={course}
              cover={coverByCourse.get(course.course_id)!}
              onSelect={onSelect}
            />
          ))}
        </div>
      </section>
    </div>
  );
}
