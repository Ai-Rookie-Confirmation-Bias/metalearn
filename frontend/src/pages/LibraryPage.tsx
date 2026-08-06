import { Link, useNavigate } from "react-router-dom";
import { useQueries } from "@tanstack/react-query";
import {
  PlusIcon,
  PlayIcon,
  PencilIcon,
  PenNibIcon,
  BookOpenIcon,
  NotebookIcon,
  GraduationCapIcon,
  BookmarkIcon,
  type Icon,
} from "@phosphor-icons/react";

import { fetchDocument, type DocumentOut } from "@/features/curriculum/api/curriculum";
import {
  curriculumKeys,
  useDocuments,
} from "@/features/curriculum/queries/useCurriculum";
import { useCreatedCourses } from "@/features/course-create/store";

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

function BookCard({ doc, cover }: { doc: DocumentOut; cover: Cover }) {
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

        <Link
          to={learnPath(doc.docId)}
          className="mt-auto inline-flex w-full items-center justify-center rounded-xl bg-primary px-5 py-3 text-[0.9rem] font-semibold text-white shadow-sm transition-all hover:bg-primary-hover hover:-translate-y-0.5 hover:shadow-md"
        >
          {cta}
        </Link>
      </div>
    </div>
  );
}

function DraftCard({
  title,
  cover,
}: {
  title: string;
  cover: Cover;
}) {
  const CoverIcon = cover.icon;
  return (
    <div className="flex min-h-[350px] flex-col overflow-hidden rounded-2xl border border-border-primary bg-white shadow-sm">
      <div
        className={`relative flex h-[140px] items-center justify-center bg-gradient-to-br text-white ${cover.grad}`}
      >
        <span className="h-9 w-9 animate-spin rounded-full border-[3px] border-white/40 border-t-white" />
      </div>
      <div className="flex flex-1 flex-col p-6">
        <h4 className="mb-1 text-[1.125rem] font-bold leading-snug text-text-primary">{title}</h4>
        <p className="mb-6 flex-1 text-[0.9rem] text-text-secondary">
          AI가 커리큘럼을 만들고 있어요…
        </p>
        <div className="mt-auto inline-flex w-full items-center justify-center gap-2 rounded-xl bg-bg-secondary px-5 py-3 text-[0.9rem] font-semibold text-text-tertiary">
          <CoverIcon className="text-base opacity-50" />
          생성 중…
        </div>
      </div>
    </div>
  );
}

export function LibraryPage() {
  const navigate = useNavigate();
  const drafts = useCreatedCourses((s) => s.drafts);
  const { data: docIds, isLoading, isError } = useDocuments();

  const docs = useQueries({
    queries: (docIds ?? []).map((id) => ({
      queryKey: curriculumKeys.document(id),
      queryFn: () => fetchDocument(id),
    })),
  });

  const ready = docs
    .map((q) => q.data)
    .filter((d): d is DocumentOut => Boolean(d));

  // 이어서 = 한 번이라도 본 자료 중 준비도가 가장 높은 것(아직 미완).
  const continueDoc = ready
    .filter((d) => sectionsDone(d) > 0 && !d.complete)
    .sort((a, b) => b.readiness - a.readiness)[0];

  const coverById = assignCovers([
    ...drafts.map((d) => d.id),
    ...ready.map((d) => d.docId),
  ]);

  const empty = !isLoading && !isError && ready.length === 0 && drafts.length === 0;

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

              {drafts.map((d) => (
                <DraftCard
                  key={d.id}
                  title={d.title}
                  cover={coverById.get(d.id) ?? COVERS[0]}
                />
              ))}

              {ready.map((doc) => (
                <BookCard
                  key={doc.docId}
                  doc={doc}
                  cover={coverById.get(doc.docId) ?? COVERS[0]}
                />
              ))}
            </div>
          )
        )}
      </section>
    </div>
  );
}
