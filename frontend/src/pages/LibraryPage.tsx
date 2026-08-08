import { useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useQueries, useQueryClient } from "@tanstack/react-query";
import {
  PlusIcon,
  PlayIcon,
  PencilIcon,
  PenNibIcon,
  BookOpenIcon,
  NotebookIcon,
  GraduationCapIcon,
  BookmarkIcon,
  CompassIcon,
  WarningCircleIcon,
  type Icon,
} from "@phosphor-icons/react";

import { fetchDocument, type DocumentOut } from "@/features/curriculum/api/curriculum";
import {
  curriculumKeys,
  useDocuments,
} from "@/features/curriculum/queries/useCurriculum";
import {
  PARSE_LABEL,
  parseProgress,
  type ParsingDocumentOut,
} from "@/features/parsing/api/documents";
import { useParsingDocuments } from "@/features/parsing/queries/useParsingDocuments";
import { usePendingUploads } from "@/features/parsing/store";
import {
  useDraftCourses,
  type DraftView,
} from "@/features/course/useDraftCourses";

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
  /** 수업인데 아직 진단을 안 했다. 진단이 목차 앞에 보강 단원을 넣으므로
   *  **학습보다 먼저** 권한다 — 나중에 하면 이미 읽은 단원 앞에 끼워진다. */
  needsDiagnostic?: boolean;
}) {
  const done = sectionsDone(doc);
  const progress = Math.round(doc.readiness * 100);
  const started = done > 0;
  const cta = started ? "이어서 학습하기" : "학습 시작하기";
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

        {needsDiagnostic ? (
          <div className="mt-auto flex flex-col gap-2">
            <Link
              to={`/diagnostic/${encodeURIComponent(doc.docId)}`}
              className="inline-flex w-full items-center justify-center gap-2 rounded-xl bg-accent px-5 py-3 text-[0.9rem] font-semibold text-white shadow-sm transition-all hover:-translate-y-0.5 hover:shadow-md"
            >
              <CompassIcon weight="fill" />
              진단 시작하기
            </Link>
            <Link
              to={learnPath(doc.docId)}
              className="inline-flex w-full items-center justify-center rounded-xl border border-border-primary px-5 py-2.5 text-[0.85rem] font-medium text-text-secondary transition-colors hover:bg-bg-secondary"
            >
              건너뛰고 학습하기
            </Link>
          </div>
        ) : (
          <Link
            to={learnPath(doc.docId)}
            className="mt-auto inline-flex w-full items-center justify-center rounded-xl bg-primary px-5 py-3 text-[0.9rem] font-semibold text-white shadow-sm transition-all hover:bg-primary-hover hover:-translate-y-0.5 hover:shadow-md"
          >
            {cta}
          </Link>
        )}
      </div>
    </div>
  );
}

/** 자료는 다 올렸는데 아직 수업이 안 된 것. 파싱이 끝나야 만들 수 있다. */
function DraftCard({ draft, cover }: { draft: DraftView; cover: Cover }) {
  const total = draft.docIds.length;
  const done = draft.statuses.filter((s) => s === "ready").length;
  const broken = draft.failed || Boolean(draft.error);
  const message = draft.error
    ? draft.error
    : draft.failed
      ? "자료 분석에 실패한 파일이 있어요."
      : draft.creating
        ? "수업으로 묶는 중…"
        : `자료 ${done}/${total}개 분석 완료`;

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
          {draft.title}
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
                style={{ width: `${total ? Math.round((done / total) * 100) : 0}%` }}
              />
            </div>
            <p className="mt-1.5 text-[0.75rem] text-text-tertiary">
              분석이 끝나면 수업으로 묶어드려요.
            </p>
          </div>
        )}
        <div className="mt-auto inline-flex w-full items-center justify-center gap-2 rounded-xl bg-bg-secondary px-5 py-3 text-[0.9rem] font-semibold text-text-tertiary">
          {broken ? "확인이 필요해요" : "준비 중…"}
        </div>
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

export function LibraryPage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const pending = usePendingUploads((s) => s.pending);
  const dropPending = usePendingUploads((s) => s.remove);
  const { data: docIds, isLoading, isError } = useDocuments();

  const docs = useQueries({
    queries: (docIds ?? []).map((id) => ({
      queryKey: curriculumKeys.document(id),
      queryFn: () => fetchDocument(id),
    })),
  });

  const parsing = useParsingDocuments(pending.map((p) => p.docId));

  // 초안 → 코스. 자료가 전부 ready가 되면 여기서 POST /courses가 나간다.
  const drafts = useDraftCourses();
  const waitingDrafts = drafts.filter((d) => !d.courseId);
  // 이 코스는 아직 진단을 안 했다 → 카드에 "진단 시작하기"를 띄운다.
  const undiagnosed = new Set(
    drafts.filter((d) => d.courseId && !d.diagnosed).map((d) => d.courseId as string),
  );

  const ready = docs
    .map((q) => q.data)
    .filter((d): d is DocumentOut => Boolean(d));

  // 파싱이 끝나도 커리큘럼 목록은 다시 물어봐야 안다 — 그 목록 API가 호출될
  // 때 ready 문서를 학습 store로 끌어오기 때문이다(파싱→학습 이음매).
  const readyKey = parsing
    .map((q) => q.data)
    .filter((d): d is ParsingDocumentOut => d?.status === "ready")
    .map((d) => d.id)
    .join(",");
  useEffect(() => {
    if (!readyKey) return;
    void qc.invalidateQueries({ queryKey: curriculumKeys.documents });
  }, [readyKey, qc]);

  // 책장이 그 자료를 알아본 뒤에야 대기 목록에서 뺀다. 먼저 빼면 카드가
  // 한 번 사라졌다가 다시 나타난다.
  useEffect(() => {
    if (!docIds) return;
    for (const p of pending) {
      if (docIds.includes(p.docId)) dropPending(p.docId);
    }
  }, [docIds, pending, dropPending]);

  // 이어서 = 한 번이라도 본 자료 중 준비도가 가장 높은 것(아직 미완).
  const continueDoc = ready
    .filter((d) => sectionsDone(d) > 0 && !d.complete)
    .sort((a, b) => b.readiness - a.readiness)[0];

  // 초안에 묶인 자료는 초안 카드가 대신 보여준다 — 같은 파일이 두 장으로
  // 뜨면 몇 개를 올렸는지 셀 수 없다.
  const inDraft = new Set(waitingDrafts.flatMap((d) => d.docIds));
  const loosePending = pending.filter((p) => !inDraft.has(p.docId));

  const coverById = assignCovers([
    ...waitingDrafts.map((d) => d.id),
    ...loosePending.map((p) => p.docId),
    ...ready.map((d) => d.docId),
  ]);

  const empty =
    !isLoading &&
    !isError &&
    ready.length === 0 &&
    pending.length === 0 &&
    waitingDrafts.length === 0;

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

              {waitingDrafts.map((d) => (
                <DraftCard key={d.id} draft={d} cover={coverById.get(d.id) ?? COVERS[0]} />
              ))}

              {loosePending.map((p) => (
                <PendingCard
                  key={p.docId}
                  filename={p.filename}
                  doc={parsing[pending.findIndex((q) => q.docId === p.docId)]?.data}
                  unreachable={Boolean(
                    parsing[pending.findIndex((q) => q.docId === p.docId)]?.isError,
                  )}
                  cover={coverById.get(p.docId) ?? COVERS[0]}
                  onDismiss={() => dropPending(p.docId)}
                />
              ))}

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
