/**
 * 수업 생성(Create Course) 위저드.
 *   STEP 1 메인 자료 → STEP 2 추가 자료(선택) → STEP 3 목표 → 업로드 → 진단으로 직행.
 * 1차 수직 완주 범위: 메인 자료 "첫 파일 1개"만 POST /api/documents/upload로 전송.
 *   TODO(ISSUE-011): 다중 메인 파일(분할 교재)·보조 자료·링크는 백엔드 코스-문서
 *   다중 연결이 생기면 배선. 지금은 UI 입력만 받고 전송하지 않는다.
 * 참고 원본: UXUI_ANT/create_course.html · 스키마: docs/SCHEMA.md
 */
import { useEffect, useRef, useState, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { clsx } from "clsx";
import {
  ArrowLeftIcon,
  UploadSimpleIcon,
  LinkIcon,
  FileIcon,
  TrashIcon,
  ArrowUpIcon,
  ArrowDownIcon,
  CertificateIcon,
  BriefcaseIcon,
  BookOpenIcon,
  SmileyIcon,
  type Icon,
} from "@phosphor-icons/react";

import { uploadDocument, uploadDocumentBatch } from "@/features/documents/api/uploadDocument";
import { apiErrorMessage } from "@/shared/api/errors";
import type { DocumentKind, Material, Purpose } from "@/features/course-create/types";

const KINDS: { value: DocumentKind; label: string }[] = [
  { value: "textbook", label: "교재" },
  { value: "slide", label: "슬라이드" },
  { value: "notes", label: "필기" },
  { value: "exam", label: "기출/문제" },
  { value: "text", label: "텍스트" },
  { value: "link", label: "링크" },
];
// 메인 자료엔 링크 제외 (링크는 보조 자료로만)
const PRIMARY_KINDS = KINDS.filter((k) => k.value !== "link");

const PURPOSES: { value: Purpose; label: string; desc: string; icon: Icon }[] = [
  { value: "exam", label: "시험 · 자격증", desc: "합격이 목표예요", icon: CertificateIcon },
  { value: "career", label: "실무 · 커리어", desc: "일에 써먹고 싶어요", icon: BriefcaseIcon },
  { value: "culture", label: "교양 · 흥미", desc: "새 분야를 알고 싶어요", icon: BookOpenIcon },
  { value: "hobby", label: "취미", desc: "재미로 배워요", icon: SmileyIcon },
];

let uid = 0;
const nextId = () => `m_${Date.now()}_${uid++}`;
const stripExt = (name: string) => name.replace(/\.[^.]+$/, "");

const cardBase = "border-2 rounded-xl bg-white cursor-pointer transition-all";
const cardState = (selected: boolean) =>
  selected
    ? "border-primary bg-black/[0.03]"
    : "border-border-primary hover:border-text-tertiary hover:bg-bg-secondary";

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
  return (
    <>
      <button
        type="button"
        onClick={() => ref.current?.click()}
        className="group flex w-full flex-col items-center justify-center rounded-xl border-2 border-dashed border-border-primary py-8 text-center transition-colors hover:border-accent hover:bg-accent/5"
      >
        <UploadSimpleIcon className="mb-2 text-[2rem] text-text-tertiary transition-colors group-hover:text-accent" />
        <span className="text-[0.9rem] font-medium text-text-secondary">{label}</span>
      </button>
      <input
        ref={ref}
        type="file"
        multiple
        hidden
        onChange={(e) => {
          if (e.target.files) onFiles(e.target.files);
          e.target.value = "";
        }}
      />
    </>
  );
}

// 자료 한 줄 (파일명 · 형태 선택 · [순서] · 삭제)
function MaterialRow({
  material,
  kinds,
  onKind,
  onRemove,
  onUp,
  onDown,
  canUp,
  canDown,
}: {
  material: Material;
  kinds: { value: DocumentKind; label: string }[];
  onKind: (k: DocumentKind) => void;
  onRemove: () => void;
  onUp?: () => void;
  onDown?: () => void;
  canUp?: boolean;
  canDown?: boolean;
}) {
  const FileTypeIcon = material.kind === "link" ? LinkIcon : FileIcon;
  return (
    <div className="flex items-center gap-3 rounded-xl border border-border-primary bg-white px-4 py-3">
      <FileTypeIcon className="shrink-0 text-lg text-text-tertiary" />
      <span className="min-w-0 flex-1 truncate text-[0.9rem] text-text-primary">{material.name}</span>

      <select
        value={material.kind}
        onChange={(e) => onKind(e.target.value as DocumentKind)}
        className="shrink-0 rounded-lg border border-border-primary bg-bg-secondary px-2 py-1 text-[0.8rem] text-text-secondary focus:outline-none"
      >
        {kinds.map((k) => (
          <option key={k.value} value={k.value}>
            {k.label}
          </option>
        ))}
      </select>

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

export function CreateCoursePage() {
  const navigate = useNavigate();

  const [step, setStep] = useState(0); // 0 메인 / 1 추가 / 2 목표
  const [primaries, setPrimaries] = useState<Material[]>([]);
  const [supps, setSupps] = useState<Material[]>([]);
  const [courseName, setCourseName] = useState(""); // 비우면 첫 파일명으로 폴백
  const [linkUrl, setLinkUrl] = useState("");
  const [purpose, setPurpose] = useState<Purpose | null>(null);
  // 업로드(파싱 포함) 상태 — Document Parse + 개념 추출이라 2~5분 걸린다.
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const addFiles = (files: FileList, role: "primary" | "supplementary") => {
    const items: Material[] = Array.from(files).map((f) => ({
      id: nextId(),
      name: f.name,
      kind: "textbook",
      role,
      file: f, // 실제 업로드용 원본 파일 보존
    }));
    (role === "primary" ? setPrimaries : setSupps)((prev) => {
      const merged = [...prev, ...items];
      // 주교재는 파일명 숫자 기준 자동 정렬(ch01·ch02·ch10 순) — 학습 순서 초안.
      // 사용자가 ↑↓로 언제든 재배열 가능(확정은 사람).
      if (role === "primary") {
        merged.sort((a, b) =>
          a.name.localeCompare(b.name, undefined, { numeric: true }),
        );
      }
      return merged;
    });
  };

  const addLink = () => {
    const url = linkUrl.trim();
    if (!url) return;
    setSupps((prev) => [...prev, { id: nextId(), name: url, kind: "link", role: "supplementary" }]);
    setLinkUrl("");
  };

  const setKind = (which: "p" | "s", id: string, kind: DocumentKind) => {
    const upd = (arr: Material[]) => arr.map((m) => (m.id === id ? { ...m, kind } : m));
    (which === "p" ? setPrimaries : setSupps)(upd);
  };
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

  const canNext = step === 0 ? primaries.length > 0 : step === 1 ? true : purpose !== null;

  const back = () => (step === 0 ? navigate("/library") : setStep((s) => s - 1));
  const next = () => {
    if (!canNext || uploading) return;
    if (step < 2) {
      setStep((s) => s + 1);
      return;
    }
    void submitCourse();
  };

  // 제출: 주교재(순서대로) + 보조자료를 하나의 코스로 업로드 → 진단으로 직행.
  // 파일 1개면 단일 업로드, 여러 개면 배치(1:N 통합). 링크(파일 없음)는 제외.
  const submitCourse = async () => {
    const primaryFiles = primaries.filter((m) => m.file);
    if (primaryFiles.length === 0) {
      setUploadError("메인 자료 파일을 다시 선택해주세요.");
      return;
    }
    setUploading(true);
    setUploadError(null);
    try {
      const suppFiles = supps.filter((m) => m.file);
      // 코스 이름: 사용자 입력 우선, 비우면 첫 주교재 파일명으로 폴백.
      const title = courseName.trim() || stripExt(primaryFiles[0].name);
      const course =
        primaryFiles.length === 1 && suppFiles.length === 0
          ? await uploadDocument(primaryFiles[0].file!, title)
          : await uploadDocumentBatch(
              [
                ...primaryFiles.map((m) => ({ file: m.file!, role: "primary" as const })),
                ...suppFiles.map((m) => ({ file: m.file!, role: "supplementary" as const })),
              ],
              title,
            );
      // 업로드 완료 → 바로 수준 진단으로 (목표는 진단 완료 시 씨앗 조립 purpose로 전달)
      navigate(`/diagnosis/${course.id}${purpose ? `?purpose=${purpose}` : ""}`);
    } catch (e) {
      setUploadError(apiErrorMessage(e));
      setUploading(false);
    }
  };

  const nextLabel = step === 2 ? (uploading ? "분석 중…" : "생성하기") : "다음";

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
              <p className="mb-8 text-[0.95rem] text-text-secondary">
                이 자료가 학습의 기준(천장)이 돼요. 여러 파일로 나뉘어 있으면 순서대로 올려주세요.
              </p>
              <UploadZone label="클릭해서 파일 선택 (여러 개 가능)" onFiles={(f) => addFiles(f, "primary")} />
              {primaries.length > 0 && (
                <div className="mt-4 flex flex-col gap-2">
                  {primaries.map((m, i) => (
                    <MaterialRow
                      key={m.id}
                      material={m}
                      kinds={PRIMARY_KINDS}
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
              {primaries.length > 0 && (
                <div className="mt-6">
                  <label className="mb-1.5 block text-[0.85rem] font-semibold text-text-secondary">
                    코스 이름
                  </label>
                  <input
                    value={courseName}
                    onChange={(e) => setCourseName(e.target.value)}
                    placeholder={stripExt(primaries[0].name)}
                    className="w-full rounded-xl border border-border-primary bg-white px-4 py-2.5 text-[0.95rem] text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
                  />
                  <p className="mt-1 text-[0.8rem] text-text-tertiary">
                    비워두면 첫 파일명(<span className="font-medium">{stripExt(primaries[0].name)}</span>)으로 정해져요.
                  </p>
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
                기출·문제, 링크, 필기 같은 보조 자료예요. 없으면 건너뛰어도 돼요.
              </p>
              <UploadZone label="파일 추가" onFiles={(f) => addFiles(f, "supplementary")} />
              <div className="mt-3 flex gap-2">
                <input
                  value={linkUrl}
                  onChange={(e) => setLinkUrl(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), addLink())}
                  placeholder="https:// 링크 붙여넣기"
                  className="flex-1 rounded-xl border border-border-primary bg-white px-4 py-2.5 text-[0.9rem] text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none"
                />
                <button
                  type="button"
                  onClick={addLink}
                  className="shrink-0 rounded-xl border border-border-primary bg-white px-4 py-2.5 text-[0.9rem] font-semibold text-text-primary transition-colors hover:bg-bg-secondary"
                >
                  추가
                </button>
              </div>
              {supps.length > 0 && (
                <div className="mt-4 flex flex-col gap-2">
                  {supps.map((m) => (
                    <MaterialRow
                      key={m.id}
                      material={m}
                      kinds={KINDS}
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
                    disabled={uploading}
                    onClick={() => setPurpose(o.value)}
                    className={clsx(
                      cardBase,
                      cardState(purpose === o.value),
                      "flex flex-col items-start gap-1 px-5 py-4 text-left",
                      uploading && "pointer-events-none opacity-60",
                    )}
                  >
                    <o.icon className="text-[1.75rem] text-primary" />
                    <span className="font-semibold text-text-primary">{o.label}</span>
                    <span className="text-[0.8rem] text-text-secondary">{o.desc}</span>
                  </button>
                ))}
              </div>

              {/* 업로드 진행 안내 — Document Parse + 개념 추출로 2~5분 소요 */}
              {uploading && (
                <div className="mt-6 flex items-start gap-3 rounded-xl border border-accent/30 bg-accent/[0.06] px-5 py-4">
                  <span className="mt-0.5 h-5 w-5 shrink-0 animate-spin rounded-full border-2 border-accent/30 border-t-accent" />
                  <div>
                    <p className="font-semibold text-text-primary">
                      AI가 자료를 읽고 개념을 뽑아내고 있어요
                    </p>
                    <p className="mt-0.5 text-[0.85rem] leading-relaxed text-text-secondary">
                      자료 분량에 따라 보통 2~5분 정도 걸려요. 이 화면을 닫지 말고
                      기다려주세요. 끝나면 바로 수준 진단으로 이동해요.
                    </p>
                  </div>
                </div>
              )}
              {uploadError && !uploading && (
                <p className="mt-4 text-[0.9rem] text-red-600">
                  업로드에 실패했어요: {uploadError} — 다시 시도해주세요.
                </p>
              )}
            </>
          )}
        </StepFade>

        <div className="mt-10 flex items-center justify-between border-t border-border-primary pt-6">
          <button
            onClick={back}
            disabled={uploading}
            className="flex items-center gap-2 text-[13.3333px] font-medium leading-[normal] text-text-secondary transition-colors hover:text-primary disabled:opacity-40"
          >
            <ArrowLeftIcon /> {step === 0 ? "책장으로" : "이전"}
          </button>
          <button
            onClick={next}
            disabled={!canNext || uploading}
            className={clsx(
              "inline-flex items-center gap-2 rounded-xl bg-primary px-5 py-[0.6rem] text-[13.3333px] font-semibold leading-[normal] text-white shadow-sm transition-all",
              canNext && !uploading
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
