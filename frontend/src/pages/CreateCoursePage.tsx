/**
 * 수업 생성(Create Course) 위저드 — 모델 B(진단 분리).
 *   STEP 1 메인 자료 → STEP 2 추가 자료(선택) → STEP 3 목표 → 책장으로.
 * 진단(바닥 찾기)은 여기 없음: 학습 화면의 진단 배너에서 별도.
 * 참고 원본: UXUI_ANT/create_course.html · 스키마: docs/SCHEMA.md
 *
 * 파일은 **고르는 순간 서버로 올라간다.** 마지막에 몰아 올리면 사용자가 목표를
 * 고르는 동안 놀고 있던 시간만큼 파싱이 늦어진다(파이프라인이 분 단위다).
 * 여기서 하는 일은 접수 + **수업 의도**를 남기는 것까지고, POST /courses는
 * 파싱이 끝난 뒤 책장이 부른다(역할·목차가 ready 이후에야 채워지므로).
 */
import { useEffect, useRef, useState, type ReactNode } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { clsx } from "clsx";
import {
  ArrowLeftIcon,
  UploadSimpleIcon,
  TrashIcon,
  ArrowUpIcon,
  ArrowDownIcon,
  CertificateIcon,
  BriefcaseIcon,
  BookOpenIcon,
  BookOpenTextIcon,
  CaretDownIcon,
  MagnifyingGlassIcon,
  SmileyIcon,
  WarningCircleIcon,
  CheckCircleIcon,
  type Icon,
} from "@phosphor-icons/react";

import type { DocumentOut } from "@/features/curriculum/api/curriculum";
import {
  canBecomeCourse,
  searchBooks,
  useSharedLibrary,
} from "@/features/curriculum/queries/useSharedLibrary";
import { usePendingCourse } from "@/features/course-create/pendingCourse";
import type {
  DocumentKind,
  Material,
  Purpose,
} from "@/features/course-create/types";
import {
  ACCEPT_EXTENSIONS,
  setDocumentKind,
  uploadDocument,
} from "@/features/parsing/api/documents";
import { usePendingUploads } from "@/features/parsing/store";

// 링크·텍스트는 뺐다 — 서버에 그걸 받는 문이 없다. 고를 수 있게 두면
// 제출할 수 없는 행이 목록에 남는다.
const KINDS: { value: DocumentKind; label: string }[] = [
  { value: "textbook", label: "교재" },
  { value: "slide", label: "슬라이드" },
  { value: "notes", label: "필기" },
  { value: "exam", label: "기출/문제" },
];

const PURPOSES: { value: Purpose; label: string; desc: string; icon: Icon }[] = [
  { value: "exam", label: "시험 · 자격증", desc: "합격이 목표예요", icon: CertificateIcon },
  { value: "career", label: "실무 · 커리어", desc: "일에 써먹고 싶어요", icon: BriefcaseIcon },
  { value: "culture", label: "교양 · 흥미", desc: "새 분야를 알고 싶어요", icon: BookOpenIcon },
  { value: "hobby", label: "취미", desc: "재미로 배워요", icon: SmileyIcon },
];

let uid = 0;
const nextId = () => `m_${Date.now()}_${uid++}`;

const cardBase = "border-2 rounded-xl bg-white cursor-pointer transition-all";
const cardState = (selected: boolean) =>
  selected
    ? "border-primary bg-black/[0.03]"
    : "border-border-primary hover:border-text-tertiary hover:bg-bg-secondary";

const uploading = (m: Material) => !m.docId && !m.error;

function formatSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function describe(error: unknown): string {
  const detail = (error as { response?: { data?: { detail?: string } } })?.response
    ?.data?.detail;
  if (detail) return detail;
  return (error as Error)?.message ?? String(error);
}

// 매 스텝 오른쪽에서 슬라이드-인 (전역 keyframe 대신 transition)
function StepFade({ children }: { children: ReactNode }) {
  const [shown, setShown] = useState(false);
  useEffect(() => {
    const id = requestAnimationFrame(() => setShown(true));
    return () => cancelAnimationFrame(id);
  }, []);
  return (
    <div
      className={clsx(
        "transition-all duration-300 ease-out",
        shown ? "opacity-100 translate-x-0" : "opacity-0 translate-x-8",
      )}
    >
      {children}
    </div>
  );
}

function UploadZone({ label, onFiles }: { label: string; onFiles: (files: FileList) => void }) {
  const ref = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setOver(false);
        if (e.dataTransfer.files.length) onFiles(e.dataTransfer.files);
      }}
    >
      <button
        type="button"
        onClick={() => ref.current?.click()}
        className={clsx(
          "group flex w-full flex-col items-center justify-center rounded-xl border-2 border-dashed py-8 text-center transition-colors",
          over
            ? "border-accent bg-accent/5"
            : "border-border-primary hover:border-accent hover:bg-accent/5",
        )}
      >
        <UploadSimpleIcon
          className={clsx(
            "mb-2 text-[2rem] transition-colors",
            over ? "text-accent" : "text-text-tertiary group-hover:text-accent",
          )}
        />
        <span className="text-[0.9rem] font-medium text-text-secondary">{label}</span>
        <span className="mt-1 text-[0.8rem] text-text-tertiary">
          PDF · 이미지(PNG · JPG · TIFF · BMP · HEIC)
        </span>
      </button>
      <input
        ref={ref}
        type="file"
        multiple
        hidden
        accept={ACCEPT_EXTENSIONS}
        onChange={(e) => {
          if (e.target.files) onFiles(e.target.files);
          e.target.value = "";
        }}
      />
    </div>
  );
}

/** 검색 전에 미리 보여줄 권수. **목록을 길게 만들 바엔 검색을 시킨다.** */
const PREVIEW = 3;
/** 결과 상한. 이보다 많으면 스크롤이 아니라 "더 좁혀 보세요"가 답이다. */
const MAX_HITS = 8;

/** MetaLearn 도서관에서 고르기 — **검색이 먼저, 목록은 나중.**
 *
 * 새 창으로 도서관에 보내지 않는다: 위저드는 셸 밖 전체화면이라 나가면 여기
 * 담아 둔 자료와 순서가 통째로 날아간다. 목록을 여기로 가져온다.
 *
 * 이미 분석이 끝난 책이라 **올리는 시간이 0이다.** 자료를 처음 올리는 사람이
 * 파싱 몇 분을 기다리지 않고 곧장 진단까지 가 볼 수 있는 유일한 길이다.
 *
 * ⚠️ **전부 늘어놓지 않는다.** 책이 백 권이면 220px 창에 백 줄이 되고, 뭘
 *    찾는지 알아도 못 찾는다. 열면 검색창에 커서가 가 있고 목록은 세 권까지만
 *    맛보기로 보인다. 나머지는 검색으로 좁혀 온다.
 *
 * 남은 한계: 목록 API가 id만 줘서 화면이 책 한 권씩 따로 가져온다(N+1).
 * 백 권이면 요청이 백 번이라, 실제로 그만큼 쌓이기 전에 목록 API가 제목·목차
 * 수를 함께 주도록 고쳐야 한다. 화면보다 이쪽이 먼저 무너진다.
 */
function LibraryPicker({
  chosen,
  onPick,
}: {
  chosen: Set<string>;
  onPick: (doc: DocumentOut) => void;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const searchRef = useRef<HTMLInputElement>(null);
  const { books, isLoading, isError } = useSharedLibrary();

  // 픽스처는 `documents` 테이블에 행이 없어 수업 재료가 못 된다. 목록에 두면
  // 골랐는데 서버가 거절하는 행이 생긴다.
  const usable = books.filter((b) => canBecomeCourse(b.docId));
  const searching = query.trim().length > 0;
  const hits = searchBooks(usable, query);
  const shown = searching ? hits.slice(0, MAX_HITS) : hits.slice(0, PREVIEW);
  const hidden = hits.length - shown.length;

  // 펼치면 바로 칠 수 있어야 한다. 검색이 주경로인데 커서를 옮기게 하면
  // 사람들은 대신 목록을 훑는다 — 그러라고 만든 화면이 아니다.
  useEffect(() => {
    if (open) searchRef.current?.focus();
  }, [open]);

  return (
    <div className="mb-4">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-3 rounded-xl border border-border-primary bg-bg-secondary px-4 py-3 text-left transition-colors hover:border-accent hover:bg-accent/5"
      >
        <BookOpenTextIcon weight="fill" className="shrink-0 text-[1.15rem] text-accent" />
        <span className="min-w-0 flex-1">
          <span className="block text-[0.9rem] font-semibold text-text-primary">
            MetaLearn 도서관에서 찾아보기
          </span>
          <span className="block text-[0.78rem] text-text-tertiary">
            이미 분석해 둔 책이라 기다릴 필요 없어요
          </span>
        </span>
        {usable.length > 0 && (
          <span className="shrink-0 rounded-full bg-white px-2.5 py-1 text-[0.75rem] font-bold text-text-secondary">
            {usable.length}권
          </span>
        )}
        <CaretDownIcon
          className={clsx(
            "shrink-0 text-text-tertiary transition-transform",
            open && "rotate-180",
          )}
        />
      </button>

      {open && (
        <div className="mt-2 overflow-hidden rounded-xl border border-border-primary">
          <div className="flex items-center gap-2 border-b border-border-primary bg-bg-secondary px-4 py-2.5">
            <MagnifyingGlassIcon className="shrink-0 text-[1rem] text-text-tertiary" />
            <input
              ref={searchRef}
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="책 제목이나 배울 내용으로 찾기"
              className="w-full bg-transparent text-[0.85rem] text-text-primary placeholder:text-text-tertiary focus:outline-none"
            />
          </div>

          {isLoading && (
            <p className="px-4 py-6 text-center text-[0.85rem] text-text-tertiary">
              도서관을 여는 중…
            </p>
          )}
          {isError && (
            <p className="px-4 py-6 text-center text-[0.85rem] text-red-600">
              도서관을 불러오지 못했어요.
            </p>
          )}
          {!isLoading && !isError && usable.length === 0 && (
            <p className="px-4 py-6 text-center text-[0.85rem] text-text-tertiary">
              아직 꽂힌 책이 없어요.
            </p>
          )}
          {!isLoading && !isError && usable.length > 0 && hits.length === 0 && (
            <p className="px-4 py-6 text-center text-[0.85rem] text-text-tertiary">
              “{query.trim()}”에 맞는 책이 없어요.
            </p>
          )}

          {shown.map(({ doc, via }) => {
            const already = chosen.has(doc.docId);
            return (
              <button
                key={doc.docId}
                type="button"
                disabled={already}
                onClick={() => onPick(doc)}
                className={clsx(
                  "flex w-full items-center gap-3 border-b border-border-primary px-4 py-3 text-left transition-colors last:border-b-0",
                  already ? "cursor-default bg-bg-secondary" : "hover:bg-accent/5",
                )}
              >
                <BookOpenIcon className="shrink-0 text-[1.05rem] text-text-tertiary" />
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-[0.88rem] font-medium text-text-primary">
                    {doc.title}
                  </span>
                  <span className="block truncate text-[0.75rem] text-text-tertiary">
                    {/* 제목엔 없는데 목록에 떴으면 왜 떴는지 말해 준다.
                        안 그러면 사용자가 검색 결과를 의심한다. */}
                    {via
                      ? `목차 “${via}”에 있어요`
                      : `목차 ${doc.chapters.length}개 · 화면 ${doc.sectionsTotal}개`}
                  </span>
                </span>
                <span
                  className={clsx(
                    "shrink-0 text-[0.8rem] font-semibold",
                    already ? "text-text-tertiary" : "text-accent",
                  )}
                >
                  {already ? "담김" : "고르기"}
                </span>
              </button>
            );
          })}

          {hidden > 0 && (
            <p className="border-t border-border-primary bg-bg-secondary px-4 py-2.5 text-[0.78rem] text-text-tertiary">
              {searching
                ? `${MAX_HITS}권만 보여요 · ${hidden}권 더 있으니 검색어를 좁혀 보세요`
                : `외 ${hidden}권 · 위에서 찾아보세요`}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

// 자료 한 줄 (파일명 · 크기/상태 · 형태 선택 · [순서] · 삭제)
function MaterialRow({
  material,
  onKind,
  onRemove,
  onUp,
  onDown,
  canUp,
  canDown,
}: {
  material: Material;
  onKind: (k: DocumentKind) => void;
  onRemove: () => void;
  onUp?: () => void;
  onDown?: () => void;
  canUp?: boolean;
  canDown?: boolean;
}) {
  const busy = uploading(material);
  return (
    <div
      className={clsx(
        "flex items-center gap-3 rounded-xl border bg-white px-4 py-3",
        material.error ? "border-red-200 bg-red-50/50" : "border-border-primary",
      )}
    >
      {busy ? (
        <span className="h-4 w-4 shrink-0 animate-spin rounded-full border-2 border-border-primary border-t-accent" />
      ) : material.error ? (
        <WarningCircleIcon weight="fill" className="shrink-0 text-lg text-red-500" />
      ) : (
        <CheckCircleIcon weight="fill" className="shrink-0 text-lg text-emerald-500" />
      )}

      <div className="min-w-0 flex-1">
        <div className="truncate text-[0.9rem] text-text-primary">{material.name}</div>
        <div
          className={clsx(
            "text-[0.75rem]",
            material.error ? "text-red-600" : "text-text-tertiary",
          )}
        >
          {material.error
            ? material.error
            : material.fromLibrary
              ? "MetaLearn 도서관 · 분석 완료"
              : busy
                ? `${formatSize(material.size)} · 올리는 중…`
                : `${formatSize(material.size)} · 접수됨`}
        </div>
      </div>

      {/* 도서관 책은 유형을 못 고른다 — 공용 문서라 여기서 바꾸면 같은 책을
          쓰는 다른 사람의 화면까지 바뀐다. 이미 분류돼 꽂힌 책이기도 하다. */}
      {!material.fromLibrary && (
        <select
          value={material.kind}
          onChange={(e) => onKind(e.target.value as DocumentKind)}
          className="shrink-0 rounded-lg border border-border-primary bg-bg-secondary px-2 py-1 text-[0.8rem] text-text-secondary focus:outline-none"
        >
          {KINDS.map((k) => (
            <option key={k.value} value={k.value}>
              {k.label}
            </option>
          ))}
        </select>
      )}

      {onUp && (
        <div className="flex shrink-0 flex-col text-sm">
          <button
            type="button"
            onClick={onUp}
            disabled={!canUp}
            className="text-text-tertiary transition-colors hover:text-primary disabled:opacity-30"
          >
            <ArrowUpIcon />
          </button>
          <button
            type="button"
            onClick={onDown}
            disabled={!canDown}
            className="text-text-tertiary transition-colors hover:text-primary disabled:opacity-30"
          >
            <ArrowDownIcon />
          </button>
        </div>
      )}
      <button
        type="button"
        onClick={onRemove}
        className="shrink-0 text-text-tertiary transition-colors hover:text-red-500"
      >
        <TrashIcon />
      </button>
    </div>
  );
}

function titleFrom(name: string) {
  return name.replace(/\.[^.]+$/, "") || name;
}

export function CreateCoursePage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const addPending = usePendingUploads((s) => s.add);
  const setPendingCourse = usePendingCourse((s) => s.set);

  const [step, setStep] = useState(0); // 0 메인 / 1 추가 / 2 목표
  const [primaries, setPrimaries] = useState<Material[]>([]);
  const [supps, setSupps] = useState<Material[]>([]);
  const [purpose, setPurpose] = useState<Purpose | null>(null);

  const patch = (id: string, changes: Partial<Material>) => {
    const upd = (arr: Material[]) =>
      arr.map((m) => (m.id === id ? { ...m, ...changes } : m));
    setPrimaries(upd);
    setSupps(upd);
  };

  const addFiles = (files: FileList, role: "primary" | "supplementary") => {
    const items: Material[] = Array.from(files).map((f) => ({
      id: nextId(),
      name: f.name,
      size: f.size,
      kind: "textbook",
      role,
    }));
    (role === "primary" ? setPrimaries : setSupps)((prev) => [...prev, ...items]);

    // 접수증(docId)만 받고 끝낸다. 파싱은 서버 백그라운드에서 계속 돈다.
    items.forEach((item, i) => {
      const file = files[i];
      uploadDocument(file)
        .then((doc) => patch(item.id, { docId: doc.id }))
        .catch((e) => patch(item.id, { error: describe(e) }));
    });
  };

  const setKind = (which: "p" | "s", id: string, kind: DocumentKind) => {
    const upd = (arr: Material[]) => arr.map((m) => (m.id === id ? { ...m, kind } : m));
    (which === "p" ? setPrimaries : setSupps)(upd);
    // 서버에도 즉시 반영 — 파싱 완료 시점의 자동 트리거가 기출(exam)을
    // 은행 생성에서 빼려면 그 전에 서버가 알아야 한다. 업로드가 아직이면
    // 건너뛴다 (제출 시 kinds로 한 번 더 확정 전달).
    const docId = [...primaries, ...supps].find((m) => m.id === id)?.docId;
    if (docId && kind !== "link" && kind !== "text")
      void setDocumentKind(docId, kind).catch(() => {});
  };
  // 서버에서 지우지는 않는다. 문서는 공용이고 지문이 같으면 재사용되므로
  // 지웠다 다시 올려도 파싱이 다시 돌지 않는다.
  const remove = (which: "p" | "s", id: string) => {
    const f = (arr: Material[]) => arr.filter((m) => m.id !== id);
    (which === "p" ? setPrimaries : setSupps)(f);
  };
  const move = (i: number, dir: -1 | 1) => {
    setPrimaries((arr) => {
      const j = i + dir;
      if (j < 0 || j >= arr.length) return arr;
      const copy = [...arr];
      [copy[i], copy[j]] = [copy[j], copy[i]];
      return copy;
    });
  };

  const all = [...primaries, ...supps];
  const accepted = all.filter((m) => m.docId);
  const busy = all.some(uploading);
  const chosen = new Set(accepted.map((m) => m.docId as string));

  /** 도서관 책을 자료 목록에 담는다. **올리지 않는다** — 이미 서버에 있는
   *  문서를 가리키기만 하므로 docId를 처음부터 들고 시작한다. */
  const addBook = (doc: DocumentOut, role: "primary" | "supplementary") => {
    if (chosen.has(doc.docId)) return;
    const item: Material = {
      id: nextId(),
      name: doc.title,
      size: 0,
      kind: "textbook",
      role,
      docId: doc.docId,
      fromLibrary: true,
    };
    (role === "primary" ? setPrimaries : setSupps)((prev) => [...prev, item]);
  };

  // 도서관에서 "이 책으로 수업 만들기"로 들어온 경우(`/create?doc=…`).
  // 제목은 목록이 와야 알 수 있어서 도착하는 대로 한 번만 담는다.
  const preset = params.get("doc");
  const presetDone = useRef(false);
  const { books: libraryBooks } = useSharedLibrary();
  useEffect(() => {
    if (presetDone.current || !preset) return;
    const book = libraryBooks.find((b) => b.docId === preset);
    if (!book) return;
    presetDone.current = true;
    addBook(book, "primary");
    // addBook은 매 렌더 새로 만들어진다 — presetDone이 한 번만 돌게 막는다.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [preset, libraryBooks]);

  const canNext =
    step === 0
      ? primaries.some((m) => m.docId)
      : step === 1
        ? true
        : purpose !== null && accepted.length > 0 && !busy;

  const back = () => (step === 0 ? navigate("/library") : setStep((s) => s - 1));
  const next = () => {
    if (!canNext) return;
    if (step < 2) {
      setStep((s) => s + 1);
      return;
    }
    // 여기서만 purpose가 필요하다. 입구에서 막으면 STEP 1·2가 안 넘어간다 —
    // purpose는 STEP 3에서야 고르는 값이라 그전엔 늘 null이다.
    // canNext가 이미 막지만 타입을 좁히려면 한 번 더 봐야 한다.
    if (!purpose) return;
    // 파일은 이미 서버에 있다. 코스는 **파싱이 끝난 뒤** 만든다 — 역할·목차가
    // ready 이후에야 채워지므로. 여기서는 의도를 남기고 책장이 폴링한다.
    //
    // ⚠️ roles는 안 보낸다. 메인/추가 ≠ skeleton/body/reference.
    // ⚠️ purpose는 진단 goal로 매핑해 코스 생성 직후 PATCH한다(책장 쪽).
    const documentIds = accepted.map((m) => m.docId as string);
    const filenames = Object.fromEntries(
      accepted.map((m) => [m.docId as string, m.name]),
    );
    // ⚠️ 도서관 책은 빼고 보낸다. kinds는 서버에서 `documents.kind`에 도장을
    //    찍는데, 그 문서는 공용이라 같은 책을 쓰는 다른 사람에게도 그대로 간다.
    const kinds = Object.fromEntries(
      accepted
        .filter((m) => !m.fromLibrary)
        .map((m) => [m.docId as string, m.kind]),
    );
    // 도서관 책의 이름은 파일명이 아니라 책 제목이다. 확장자를 떼는 정규식이
    // "1. 인공지능 개론" 같은 제목을 "1"로 잘라 버린다.
    const head = primaries.find((m) => m.docId) ?? accepted[0];
    const title = head.fromLibrary ? head.name : titleFrom(head.name);

    setPendingCourse({ documentIds, filenames, title, purpose, kinds });
    addPending(accepted.map((m) => ({ docId: m.docId as string, filename: m.name })));
    navigate("/library");
  };

  const nextLabel = step === 2 ? "생성하기" : "다음";

  return (
    <div className="flex min-h-screen items-center justify-center bg-bg-secondary px-4">
      <div className="relative w-full max-w-[600px] overflow-hidden rounded-2xl border border-border-primary bg-white p-12 shadow-lg max-[480px]:p-6">
        <div className="mb-4 text-sm font-semibold text-accent">STEP {step + 1} / 3</div>

        <StepFade key={step}>
          {step === 0 && (
            <>
              <h2 className="mb-2 text-[1.75rem] font-bold tracking-tight text-primary">
                메인이 되는 자료를 올려주세요
              </h2>
              <p className="mb-6 text-[0.95rem] text-text-secondary">
                이 자료가 학습의 기준(천장)이 돼요. 여러 파일로 나뉘어 있으면 순서대로 올려주세요.
              </p>
              <LibraryPicker chosen={chosen} onPick={(b) => addBook(b, "primary")} />
              <UploadZone
                label="클릭하거나 파일을 여기로 드래그하세요 (여러 개 가능)"
                onFiles={(f) => addFiles(f, "primary")}
              />
              {primaries.length > 0 && (
                <div className="mt-4 flex flex-col gap-2">
                  {primaries.map((m, i) => (
                    <MaterialRow
                      key={m.id}
                      material={m}
                      onKind={(k) => setKind("p", m.id, k)}
                      onRemove={() => remove("p", m.id)}
                      onUp={() => move(i, -1)}
                      onDown={() => move(i, 1)}
                      canUp={i > 0}
                      canDown={i < primaries.length - 1}
                    />
                  ))}
                </div>
              )}
            </>
          )}

          {step === 1 && (
            <>
              <h2 className="mb-2 text-[1.75rem] font-bold tracking-tight text-primary">
                추가 자료가 있으면 올려주세요{" "}
                <span className="text-[1.1rem] font-medium text-text-tertiary">(선택)</span>
              </h2>
              <p className="mb-8 text-[0.95rem] text-text-secondary">
                기출·문제, 필기 같은 보조 자료예요. 없으면 건너뛰어도 돼요.
              </p>
              <UploadZone label="파일 추가" onFiles={(f) => addFiles(f, "supplementary")} />
              {supps.length > 0 && (
                <div className="mt-4 flex flex-col gap-2">
                  {supps.map((m) => (
                    <MaterialRow
                      key={m.id}
                      material={m}
                      onKind={(k) => setKind("s", m.id, k)}
                      onRemove={() => remove("s", m.id)}
                    />
                  ))}
                </div>
              )}
            </>
          )}

          {step === 2 && (
            <>
              <h2 className="mb-2 text-[1.75rem] font-bold tracking-tight text-primary">
                왜 배우세요?
              </h2>
              <p className="mb-8 text-[0.95rem] text-text-secondary">
                목표에 맞춰 난이도와 문제 유형을 조절해요.
              </p>
              <div className="grid grid-cols-2 gap-3 max-[480px]:grid-cols-1">
                {PURPOSES.map((o) => (
                  <button
                    key={o.value}
                    onClick={() => setPurpose(o.value)}
                    className={clsx(
                      cardBase,
                      cardState(purpose === o.value),
                      "flex flex-col items-start gap-1 px-5 py-4 text-left",
                    )}
                  >
                    <o.icon className="text-[1.75rem] text-primary" />
                    <span className="font-semibold text-text-primary">{o.label}</span>
                    <span className="text-[0.8rem] text-text-secondary">{o.desc}</span>
                  </button>
                ))}
              </div>
              {busy && (
                <p className="mt-6 text-[0.85rem] text-text-tertiary">
                  자료를 아직 올리는 중이에요. 끝나면 생성할 수 있어요.
                </p>
              )}
            </>
          )}
        </StepFade>

        <div className="mt-10 flex items-center justify-between border-t border-border-primary pt-6">
          <button
            onClick={back}
            className="flex items-center gap-2 text-[13.3333px] font-medium leading-[normal] text-text-secondary transition-colors hover:text-primary"
          >
            <ArrowLeftIcon /> {step === 0 ? "책장으로" : "이전"}
          </button>
          <button
            onClick={next}
            disabled={!canNext}
            className={clsx(
              "inline-flex items-center gap-2 rounded-xl bg-primary px-5 py-[0.6rem] text-[13.3333px] font-semibold leading-[normal] text-white shadow-sm transition-all",
              canNext
                ? "hover:-translate-y-0.5 hover:bg-primary-hover hover:shadow-md"
                : "cursor-not-allowed opacity-50",
            )}
          >
            {nextLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
