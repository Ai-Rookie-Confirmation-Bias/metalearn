import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useQueries, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  PlusIcon,
  PlayIcon,
  PencilIcon,
  PenNibIcon,
  BookOpenIcon,
  NotebookIcon,
  GraduationCapIcon,
  BookmarkIcon,
  WarningCircleIcon,
  type Icon,
} from "@phosphor-icons/react";

import { createCourse, listCourses } from "@/features/course/api";
import {
  purposeToGoal,
  usePendingCourse,
  type PendingCourse,
} from "@/features/course-create/pendingCourse";
import { fetchDocument, type DocumentOut } from "@/features/curriculum/api/curriculum";
import {
  curriculumKeys,
  useDocuments,
} from "@/features/curriculum/queries/useCurriculum";
import { saveConfig } from "@/features/diagnostic/api";
import { requestGeneration } from "@/pages/quiz/api";
import {
  PARSE_LABEL,
  parseProgress,
  type ParsingDocumentOut,
} from "@/features/parsing/api/documents";
import { useParsingDocuments } from "@/features/parsing/queries/useParsingDocuments";
import { usePendingUploads } from "@/features/parsing/store";

// 커버(색+아이콘)는 표현 계층. docId로 파생해 책장 안에서 안 겹치게.
type Cover = { grad: string; icon: Icon };
const COVERS: Cover[] = [
  { grad: "from-[#0f172a] to-[#334155]", icon: PencilIcon },
  { grad: "from-[#059669] to-[#10b981]", icon: BookOpenIcon },
  { grad: "from-[#7c3aed] to-[#a855f7]", icon: PenNibIcon },
  { grad: "from-[#d97706] to-[#f59e0b]", icon: NotebookIcon },
  { grad: "from-[#e11d48] to-[#fb7185]", icon: GraduationCapIcon },
  { grad: "from-[#0d9488] to-[#14b8a6]", icon: BookmarkIcon },
];

function hashIndex(id: string) {
  return [...id].reduce((sum, ch) => sum + ch.charCodeAt(0), 0) % COVERS.length;
}

function assignCovers(ids: string[]): Map<string, Cover> {
  const used = new Set<number>();
  const map = new Map<string, Cover>();
  for (const id of ids) {
    let idx = hashIndex(id);
    for (let i = 0; used.has(idx) && i < COVERS.length; i++) {
      idx = (idx + 1) % COVERS.length;
    }
    used.add(idx);
    map.set(id, COVERS[idx]);
  }
  return map;
}

function learnPath(docId: string) {
  return `/curriculum/${encodeURIComponent(docId)}`;
}

function sectionsDone(doc: DocumentOut) {
  return Math.max(0, doc.sectionsTotal - doc.remainingSections);
}

function ContinueBanner({ doc }: { doc: DocumentOut }) {
  const progress = Math.round(doc.readiness * 100);
  const next = doc.chapters.find((ch) => ch.sectionsDone < ch.sectionsTotal);

  return (
    <section className="mb-12 flex flex-col gap-6 rounded-2xl bg-accent p-8 text-white sm:flex-row sm:items-center sm:justify-between">
      <div className="min-w-0">
        <span className="inline-block rounded-full bg-white/10 px-3 py-1 text-xs font-semibold text-white/80">
          이어서 학습하기
        </span>
        <h3 className="mt-3 truncate text-2xl font-bold">{doc.title}</h3>
        {next && (
          <p className="mt-1 truncate text-sm text-white/60">다음: {next.title}</p>
        )}
        {doc.sectionsDue > 0 && (
          <p className="mt-1 text-sm text-white/70">🔁 복습할 화면 {doc.sectionsDue}개</p>
        )}
        <div className="mt-4 flex items-center gap-3">
          <div className="h-2 w-48 max-w-full overflow-hidden rounded-full bg-white/25">
            <div className="h-full rounded-full bg-white" style={{ width: `${progress}%` }} />
          </div>
          <span className="text-sm font-semibold text-white/80">준비도 {progress}%</span>
        </div>
      </div>

      <Link
        to={learnPath(doc.docId)}
        className="inline-flex flex-shrink-0 items-center justify-center gap-2 rounded-xl bg-white px-7 py-3.5 text-[0.95rem] font-bold text-accent shadow-sm transition-all hover:-translate-y-0.5 hover:shadow-md"
      >
        <PlayIcon weight="fill" />
        이어서 학습하기
      </Link>
    </section>
  );
}

function BookCard({
  doc,
  cover,
  needsDiagnostic,
}: {
  doc: DocumentOut;
  cover: Cover;
  /** 수업인데 진단을 아직 안 했다. **학습보다 먼저** 보낸다 — 진단이 목차 앞에
   *  보강 단원을 끼우므로, 나중에 하면 이미 읽은 단원 앞에 끼워진다. */
  needsDiagnostic?: boolean;
}) {
  const done = sectionsDone(doc);
  const progress = Math.round(doc.readiness * 100);
  const started = done > 0;
  const cta = needsDiagnostic
    ? "진단하고 시작하기"
    : started
      ? "이어서 학습하기"
      : "학습 시작하기";
  const to = needsDiagnostic
    ? `/diagnostic/${encodeURIComponent(doc.docId)}`
    : learnPath(doc.docId);
  const CoverIcon = cover.icon;

  return (
    <div className="flex min-h-[350px] flex-col overflow-hidden rounded-2xl border border-border-primary bg-white shadow-sm transition-all hover:-translate-y-1 hover:border-text-tertiary hover:shadow-lg">
      <div
        className={`relative flex h-[140px] items-center justify-center bg-gradient-to-br text-white ${cover.grad}`}
      >
        <CoverIcon className="text-[3.5rem] opacity-90" />
        <span className="absolute right-4 top-4 rounded-full bg-white/20 px-3 py-1 text-xs font-bold backdrop-blur-sm">
          화면 {doc.sectionsTotal}개
        </span>
      </div>

      <div className="flex flex-1 flex-col p-6">
        <h4 className="mb-1 text-[1.125rem] font-bold leading-snug text-text-primary">
          {doc.title}
        </h4>
        <p className="mb-6 flex-1 text-[0.9rem] text-text-secondary">
          목차 {doc.chapters.length}개 · 약 {doc.estimatedMinutes}분
          {doc.sectionsDue > 0 ? ` · 🔁 ${doc.sectionsDue}` : ""}
        </p>

        {started ? (
          <div className="mb-4">
            <div className="mb-2 flex justify-between text-[0.85rem] font-semibold">
              <span className="text-text-secondary">준비도</span>
              <span className="text-primary">{progress}%</span>
            </div>
            <div className="h-2 w-full overflow-hidden rounded-full bg-bg-secondary">
              <div
                className="h-full rounded-full bg-accent transition-all"
                style={{ width: `${progress}%` }}
              />
            </div>
            <p className="mt-1.5 text-[0.75rem] text-text-tertiary">
              {done}/{doc.sectionsTotal} 화면
            </p>
          </div>
        ) : (
          <div className="mb-4 text-[0.85rem] text-text-tertiary">아직 시작하지 않았어요</div>
        )}

        <Link
          to={to}
          className="mt-auto inline-flex w-full items-center justify-center rounded-xl bg-primary px-5 py-3 text-[0.9rem] font-semibold text-white shadow-sm transition-all hover:bg-primary-hover hover:-translate-y-0.5 hover:shadow-md"
        >
          {cta}
        </Link>
      </div>
    </div>
  );
}

// 올렸지만 아직 안 끝난 자료. **여기 보이는 건 전부 서버가 준 status다** —
// 화면이 시간을 재거나 단계를 추측하지 않는다.
function PendingCard({
  filename,
  doc,
  unreachable,
  cover,
  onDismiss,
}: {
  filename: string;
  doc: ParsingDocumentOut | undefined;
  unreachable: boolean;
  cover: Cover;
  onDismiss: () => void;
}) {
  const failed = doc?.status === "failed";
  const broken = failed || unreachable;
  const progress = doc ? Math.round(parseProgress(doc.status) * 100) : 0;
  const message = failed
    ? (doc?.error ?? PARSE_LABEL.failed)
    : unreachable
      ? "상태를 확인할 수 없어요. 백엔드가 켜져 있는지 확인해 주세요."
      : doc
        ? PARSE_LABEL[doc.status]
        : "상태를 확인하는 중…";

  return (
    <div className="flex min-h-[350px] flex-col overflow-hidden rounded-2xl border border-border-primary bg-white shadow-sm">
      <div
        className={
          broken
            ? "relative flex h-[140px] items-center justify-center bg-gradient-to-br from-[#7f1d1d] to-[#b91c1c] text-white"
            : `relative flex h-[140px] items-center justify-center bg-gradient-to-br text-white ${cover.grad}`
        }
      >
        {broken ? (
          <WarningCircleIcon weight="fill" className="text-[3.5rem] opacity-90" />
        ) : (
          <span className="h-9 w-9 animate-spin rounded-full border-[3px] border-white/40 border-t-white" />
        )}
      </div>

      <div className="flex flex-1 flex-col p-6">
        <h4 className="mb-1 truncate text-[1.125rem] font-bold leading-snug text-text-primary">
          {filename}
        </h4>
        <p
          className={`mb-6 flex-1 text-[0.9rem] ${broken ? "text-red-600" : "text-text-secondary"}`}
        >
          {message}
        </p>

        {!broken && (
          <div className="mb-4">
            <div className="h-2 w-full overflow-hidden rounded-full bg-bg-secondary">
              <div
                className="h-full rounded-full bg-accent transition-all"
                style={{ width: `${progress}%` }}
              />
            </div>
            <p className="mt-1.5 text-[0.75rem] text-text-tertiary">
              분석이 끝나면 자동으로 책장에 꽂혀요.
            </p>
          </div>
        )}

        {broken ? (
          <button
            type="button"
            onClick={onDismiss}
            className="mt-auto inline-flex w-full items-center justify-center rounded-xl border border-border-primary px-5 py-3 text-[0.9rem] font-semibold text-text-secondary transition-colors hover:bg-bg-secondary"
          >
            치우기
          </button>
        ) : (
          <div className="mt-auto inline-flex w-full items-center justify-center gap-2 rounded-xl bg-bg-secondary px-5 py-3 text-[0.9rem] font-semibold text-text-tertiary">
            분석 중…
          </div>
        )}
      </div>
    </div>
  );
}

// 위저드가 남긴 수업 의도 — 자료 N개를 한 권으로 묶는 중.
function PendingCourseCard({
  course,
  docs,
  error,
  cover,
  onDismiss,
}: {
  course: PendingCourse;
  docs: (ParsingDocumentOut | undefined)[];
  error: string | null;
  cover: Cover;
  onDismiss: () => void;
}) {
  const failed = docs.some((d) => d?.status === "failed");
  const readyCount = docs.filter((d) => d?.status === "ready").length;
  const total = course.documentIds.length;
  const progress = total
    ? Math.round(
        (docs.reduce((sum, d) => sum + (d ? parseProgress(d.status) : 0), 0) / total) * 100,
      )
    : 0;
  const broken = failed || Boolean(error);
  const names = course.documentIds
    .map((id) => course.filenames[id])
    .filter(Boolean)
    .join(" · ");

  return (
    <div className="flex min-h-[350px] flex-col overflow-hidden rounded-2xl border border-border-primary bg-white shadow-sm">
      <div
        className={
          broken
            ? "relative flex h-[140px] items-center justify-center bg-gradient-to-br from-[#7f1d1d] to-[#b91c1c] text-white"
            : `relative flex h-[140px] items-center justify-center bg-gradient-to-br text-white ${cover.grad}`
        }
      >
        {broken ? (
          <WarningCircleIcon weight="fill" className="text-[3.5rem] opacity-90" />
        ) : (
          <span className="h-9 w-9 animate-spin rounded-full border-[3px] border-white/40 border-t-white" />
        )}
        <span className="absolute right-4 top-4 rounded-full bg-white/20 px-3 py-1 text-xs font-bold backdrop-blur-sm">
          자료 {readyCount}/{total}
        </span>
      </div>

      <div className="flex flex-1 flex-col p-6">
        <h4 className="mb-1 truncate text-[1.125rem] font-bold leading-snug text-text-primary">
          {course.title}
        </h4>
        <p
          className={`mb-2 flex-1 text-[0.9rem] ${broken ? "text-red-600" : "text-text-secondary"}`}
        >
          {error
            ? error
            : failed
              ? "자료 분석에 실패한 파일이 있어요."
              : readyCount === total
                ? "수업을 묶는 중…"
                : "자료를 분석한 뒤 수업 한 권으로 묶어요."}
        </p>
        <p className="mb-6 truncate text-[0.75rem] text-text-tertiary">{names}</p>

        {!broken && (
          <div className="mb-4">
            <div className="h-2 w-full overflow-hidden rounded-full bg-bg-secondary">
              <div
                className="h-full rounded-full bg-accent transition-all"
                style={{ width: `${progress}%` }}
              />
            </div>
          </div>
        )}

        {broken ? (
          <button
            type="button"
            onClick={onDismiss}
            className="mt-auto inline-flex w-full items-center justify-center rounded-xl border border-border-primary px-5 py-3 text-[0.9rem] font-semibold text-text-secondary transition-colors hover:bg-bg-secondary"
          >
            치우기
          </button>
        ) : (
          <div className="mt-auto inline-flex w-full items-center justify-center gap-2 rounded-xl bg-bg-secondary px-5 py-3 text-[0.9rem] font-semibold text-text-tertiary">
            수업 준비 중…
          </div>
        )}
      </div>
    </div>
  );
}

export function LibraryPage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const pending = usePendingUploads((s) => s.pending);
  const dropPending = usePendingUploads((s) => s.remove);
  const pendingCourse = usePendingCourse((s) => s.pending);
  const clearPendingCourse = usePendingCourse((s) => s.clear);
  const { data: docIds, isLoading, isError } = useDocuments();
  const [assembleError, setAssembleError] = useState<string | null>(null);
  const assembling = useRef(false);

  const courseDocIds = new Set(pendingCourse?.documentIds ?? []);
  // 수업으로 묶을 자료는 개별 대기 카드로 안 띄운다 — 한 장의 "수업 준비 중"으로.
  const lonePending = pending.filter((p) => !courseDocIds.has(p.docId));

  const docs = useQueries({
    queries: (docIds ?? []).map((id) => ({
      queryKey: curriculumKeys.document(id),
      queryFn: () => fetchDocument(id),
    })),
  });

  // **코스 목록 한 번으로 진단 여부를 안다.** 카드마다 따로 물으면 자료 수만큼
  // 요청이 나가고, 자료 하나짜리는 404라 콘솔이 지저분해진다.
  const { data: courses } = useQuery({
    queryKey: ["courses", "list"],
    queryFn: listCourses,
    staleTime: 10_000,
  });
  const undiagnosed = new Set(
    (courses ?? []).filter((c) => !c.diagnosed_at).map((c) => c.id),
  );

  const parsing = useParsingDocuments(pending.map((p) => p.docId));
  const parsingById = new Map(
    parsing
      .map((q) => q.data)
      .filter((d): d is ParsingDocumentOut => Boolean(d))
      .map((d) => [d.id, d]),
  );
  // effect 의존성용 — Map은 매 렌더 새 객체라 키가 바뀌는 문자열로 본다.
  const courseStatusKey = (pendingCourse?.documentIds ?? [])
    .map((id) => `${id}:${parsingById.get(id)?.status ?? "?"}`)
    .join("|");

  // 수업으로 묶기 직전인 자료는 책 카드로 안 띄운다 — 코스가 생기면 멤버로 빠진다.
  const ready = docs
    .map((q) => q.data)
    .filter((d): d is DocumentOut => Boolean(d) && !courseDocIds.has(d!.docId));

  // 파싱이 끝나도 커리큘럼 목록은 다시 물어봐야 안다 — 그 목록 API가 호출될
  // 때 ready 문서를 학습 store로 끌어오기 때문이다(파싱→학습 이음매).
  // 다만 곧 코스로 묶일 자료는 목록을 당겨도 개별 카드가 되므로, 코스 조립이
  // 끝난 뒤에만 무효화한다(아래 assemble effect).
  const readyKey = parsing
    .map((q) => q.data)
    .filter(
      (d): d is ParsingDocumentOut =>
        d?.status === "ready" && !courseDocIds.has(d.id),
    )
    .map((d) => d.id)
    .join(",");
  useEffect(() => {
    if (!readyKey) return;
    void qc.invalidateQueries({ queryKey: curriculumKeys.documents });
  }, [readyKey, qc]);

  // 책장이 그 자료를 알아본 뒤에야 대기 목록에서 뺀다. 먼저 빼면 카드가
  // 한 번 사라졌다가 다시 나타난다. 코스 멤버 후보는 조립이 뺄 때까지 둔다.
  useEffect(() => {
    if (!docIds) return;
    for (const p of lonePending) {
      if (docIds.includes(p.docId)) dropPending(p.docId);
    }
  }, [docIds, lonePending, dropPending]);

  // 전부 ready면 POST /courses. 역할은 서버가 정하고, purpose는 진단 goal로만 넘긴다.
  useEffect(() => {
    if (!pendingCourse || assembling.current || assembleError) return;
    const statuses = pendingCourse.documentIds.map((id) => parsingById.get(id));
    if (statuses.some((d) => !d)) return;
    if (statuses.some((d) => d!.status === "failed")) return;
    if (!statuses.every((d) => d!.status === "ready")) return;

    assembling.current = true;
    const { documentIds, title, purpose } = pendingCourse;
    void (async () => {
      try {
        const course = await createCourse({ document_ids: documentIds, title });
        try {
          await saveConfig(course.id, { goal: purposeToGoal(purpose) });
        } catch {
          // 목표는 진단 화면에서 다시 고를 수 있다. 코스 자체가 만들어진 게 본전.
        }

        // 문제은행 생성을 **여기서** 접수한다. 실데이터 888초짜리라 진단을
        // 하는 동안 서버가 만들게 두는 게 가장 빠르다. 이 문을 아무도 안 불러서
        // 문제집이 계속 비어 있었다.
        // 실패해도 넘어간다 — 문제집은 학습과 별개고, 문제집 화면에서 다시
        // 접수할 수 있다(리필).
        for (const id of documentIds) {
          void requestGeneration(course.id, id).catch(() => {});
        }

        for (const id of documentIds) dropPending(id);
        clearPendingCourse();
        setAssembleError(null);
        await qc.invalidateQueries({ queryKey: curriculumKeys.documents });

        // ★ 진단으로 데려간다. 진단은 **커리큘럼을 정하는 단계**지 선택지가
        //   아니다 — 건너뛰면 보강 단원 없이 배우게 된다(실측: 목차 4 → 14).
        //   방금 올린 사람만 여기 온다(`pendingCourse`가 있어야 이 블록이 돈다).
        navigate(`/diagnostic/${encodeURIComponent(course.id)}`);
      } catch (e) {
        const detail = (e as { response?: { data?: { detail?: string } } })?.response
          ?.data?.detail;
        setAssembleError(detail ?? (e as Error)?.message ?? "수업을 만들지 못했어요.");
      } finally {
        assembling.current = false;
      }
    })();
    // parsingById는 courseStatusKey로 대표한다.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pendingCourse, courseStatusKey, assembleError, dropPending, clearPendingCourse, qc]);

  // 이어서 = 한 번이라도 본 자료 중 준비도가 가장 높은 것(아직 미완).
  const continueDoc = ready
    .filter((d) => sectionsDone(d) > 0 && !d.complete)
    .sort((a, b) => b.readiness - a.readiness)[0];

  const coverById = assignCovers([
    ...(pendingCourse ? [pendingCourse.title] : []),
    ...lonePending.map((p) => p.docId),
    ...ready.map((d) => d.docId),
  ]);

  const empty =
    !isLoading &&
    !isError &&
    ready.length === 0 &&
    lonePending.length === 0 &&
    !pendingCourse;

  return (
    <div className="mx-auto w-full max-w-[1400px] px-12 py-12">
      <div className="mb-10">
        <h2 className="mb-1 text-[2rem] font-extrabold tracking-tight text-text-primary">
          오늘도 성장할 준비 되셨나요?
        </h2>
        <p className="text-text-secondary">자료를 고르면 맞춤 커리큘럼으로 들어갑니다.</p>
      </div>

      {continueDoc && <ContinueBanner doc={continueDoc} />}

      <section>
        <div className="mb-6 flex items-end justify-between">
          <h3 className="text-xl font-bold text-text-primary">나의 책장</h3>
        </div>

        {isLoading && (
          <p className="py-12 text-center text-text-secondary">자료를 불러오는 중…</p>
        )}
        {isError && (
          <p className="py-12 text-center text-red-600">
            자료를 불러오지 못했습니다. 백엔드가 켜져 있는지 확인해 주세요.
          </p>
        )}

        {!isLoading && !isError && empty ? (
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
          !isLoading &&
          !isError && (
            <div className="grid grid-cols-[repeat(auto-fill,minmax(300px,1fr))] gap-8">
              <button
                type="button"
                onClick={() => navigate("/create")}
                className="group flex min-h-[350px] flex-col items-center justify-center rounded-2xl border-2 border-dashed border-border-primary p-8 text-center transition-colors hover:border-accent hover:bg-accent/5"
              >
                <div className="mb-5 flex h-16 w-16 items-center justify-center rounded-full bg-bg-secondary text-[2rem] text-text-tertiary transition-colors group-hover:bg-accent group-hover:text-white">
                  <PlusIcon />
                </div>
                <h4 className="mb-1 text-[1.125rem] font-bold text-text-primary">
                  새로운 학습 시작하기
                </h4>
                <p className="text-[0.9rem] text-text-secondary">새 자료를 책장에 꽂아보세요.</p>
              </button>

              {pendingCourse && (
                <PendingCourseCard
                  course={pendingCourse}
                  docs={pendingCourse.documentIds.map((id) => parsingById.get(id))}
                  error={assembleError}
                  cover={coverById.get(pendingCourse.title) ?? COVERS[0]}
                  onDismiss={() => {
                    for (const id of pendingCourse.documentIds) dropPending(id);
                    clearPendingCourse();
                    setAssembleError(null);
                  }}
                />
              )}

              {lonePending.map((p) => {
                const q = parsing.find((row) => row.data?.id === p.docId);
                return (
                  <PendingCard
                    key={p.docId}
                    filename={p.filename}
                    doc={parsingById.get(p.docId) ?? q?.data}
                    unreachable={Boolean(q?.isError)}
                    cover={coverById.get(p.docId) ?? COVERS[0]}
                    onDismiss={() => dropPending(p.docId)}
                  />
                );
              })}

              {ready.map((doc) => (
                <BookCard
                  key={doc.docId}
                  doc={doc}
                  cover={coverById.get(doc.docId) ?? COVERS[0]}
                  needsDiagnostic={undiagnosed.has(doc.docId)}
                />
              ))}
            </div>
          )
        )}
      </section>
    </div>
  );
}
