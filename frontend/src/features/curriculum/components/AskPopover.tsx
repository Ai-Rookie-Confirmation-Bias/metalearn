// 본문에서 끌어 놓으면 뜨는 퀵메뉴와 답 말풍선.
//
// **채팅창을 옆에 세우지 않는다.** 입력창이 늘 열려 있으면 "질문할 게 있으면
// 쳐라"가 되는데, 대부분은 무엇을 물어야 할지 몰라서 안 묻는다. 모르는 말에
// 손이 먼저 가는 건 드래그다 — 거기서 시작한다.
//
// 답도 오른쪽 서랍이 아니라 **끌어 놓은 자리 바로 밑**에 띄운다. 시선이 안
// 움직여야 "이 말 → 이 설명"이 이어진다.
//
// ⚠️ 끄는 자리를 가린다. 빈칸·객관식 위에서 뜨면 답을 물어보는 통로가 된다 —
//    그쪽 DOM에 `data-no-ask`를 박아 두고 여기서 거른다.
import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from "react";
import { useMutation } from "@tanstack/react-query";
import {
  SparkleIcon,
  XIcon,
  PaperPlaneRightIcon,
  BookOpenTextIcon,
  BooksIcon,
  FileTextIcon,
} from "@phosphor-icons/react";

import {
  askAboutSelection,
  MAX_SELECTION,
  type AskSource,
  type AskTurn,
} from "@/features/curriculum/api/ask";

/** 이보다 짧으면 무시한다. 한 글자 드래그는 대개 실수이거나 커서 이동이다. */
const MIN_SELECTION = 2;
/** 프롬프트에 실을 앞뒤 문맥. 문단 하나면 충분하고 넘치면 서버가 자른다. */
const MAX_CONTEXT = 600;

/** 끌어 놓은 글자의 자리(뷰포트 좌표). 점이 아니라 **네모**여야 한다 —
 *  아래에 자리가 없을 때 위로 뒤집으려면 위쪽 변도 알아야 한다. */
type Anchor = { top: number; bottom: number; left: number; right: number };

/** 글자와 상자 사이. */
const GAP = 8;
/** 화면 가장자리에서 이만큼은 띄운다. */
const EDGE = 12;

function clamp(value: number, min: number, max: number) {
  return Math.max(min, Math.min(max, value));
}

/** 상자를 어디에 놓을지 — **재서 정한다.**
 *
 * 처음엔 높이를 상수(260)로 어림했는데, 화면 아래쪽에서 끌면 그 어림값이
 * 틀려서 상자가 끌어 놓은 자리와 아무 상관 없는 데로 튀었다. 게다가 답이
 * 도착하면 상자가 커지므로 **높이는 렌더 전에는 알 수 없다.**
 *
 * 그래서 그리기 전에(`useLayoutEffect`) 실제 크기를 재고, 크기가 바뀌면
 * (`ResizeObserver`) 다시 잰다. 규칙은 둘뿐이다:
 *
 *     세로   아래에 자리가 있으면 아래, 없으면 **위로 뒤집는다**
 *     가로   선택 가운데에 맞추되 화면 밖으로 안 나가게 민다
 */
function usePlacement(
  anchor: Anchor | null,
  boxRef: React.RefObject<HTMLElement | null>,
  /** 상자 **엘리먼트가 바뀔 때** 같이 바뀌는 값. 퀵메뉴(작은 버튼)와 말풍선은
   *  서로 다른 노드라, 이게 없으면 말풍선이 버튼 자리를 그대로 물려받는다 —
   *  버튼 기준으로 잡힌 자리라 말풍선 높이만큼 화면 아래로 넘친다. */
  node: unknown,
) {
  const [pos, setPos] = useState<{ left: number; top: number } | null>(null);

  useLayoutEffect(() => {
    const box = boxRef.current;
    if (!anchor || !box) {
      setPos(null);
      return;
    }

    const place = () => {
      const { width, height } = box.getBoundingClientRect();

      const below = anchor.bottom + GAP;
      const above = anchor.top - GAP - height;
      let top = below;
      if (below + height > window.innerHeight - EDGE) {
        // 위가 되면 위로, 위도 안 되면(상자가 화면보다 큼) 아래 끝에 붙인다.
        top =
          above >= EDGE
            ? above
            : Math.max(EDGE, window.innerHeight - EDGE - height);
      }

      const center = (anchor.left + anchor.right) / 2;
      const left = clamp(
        center - width / 2,
        EDGE,
        Math.max(EDGE, window.innerWidth - EDGE - width),
      );

      setPos((prev) =>
        prev && prev.left === left && prev.top === top ? prev : { left, top },
      );
    };

    place();
    const observer = new ResizeObserver(place);
    observer.observe(box);
    window.addEventListener("resize", place);
    return () => {
      observer.disconnect();
      window.removeEventListener("resize", place);
    };
  }, [anchor, boxRef, node]);

  return pos;
}

/** 끌어 놓은 곳이 속한 문단 — **끌어 놓은 자리를 가운데 두고** 자른다.
 *
 * 처음엔 문단 맨 앞에서 600자를 잘랐다. 그러면 긴 문단의 **뒷부분을 끌었을 때
 * 끌어 놓은 말 자체가 문맥에서 빠진다.** 설명 본문은 `<p>` 하나에 통째로
 * 들어가서(`Explanation.tsx`) 문단이 길어지기 쉬운 자리다.
 *
 * 앞에서 자르지 않는 건 `blocks.clip_around`가 원문에 하는 것과 같은 발상이다 —
 * 거기서도 앞에서 자르니 뒤쪽 개념이 통째로 사라졌다.
 */
function contextOf(range: Range): string {
  const node =
    range.commonAncestorContainer.nodeType === Node.ELEMENT_NODE
      ? (range.commonAncestorContainer as Element)
      : range.commonAncestorContainer.parentElement;
  const block = node?.closest("p, li, pre, h1, h2, h3, td, blockquote");
  if (!block) return "";
  const text = block.textContent ?? "";
  if (text.length <= MAX_CONTEXT) return text.trim();

  // 문단 안에서 끌어 놓은 말이 **몇 번째 글자에서 시작하나.**
  // 글자로 다시 찾지(indexOf) 않는다 — 같은 말이 문단에 두 번 나오면 엉뚱한
  // 자리를 가운데로 잡는다. 범위 자체가 답을 갖고 있다.
  const before = document.createRange();
  before.selectNodeContents(block);
  before.setEnd(range.startContainer, range.startOffset);
  const at = before.toString().length;

  const picked = range.toString().length;
  const half = Math.max(0, Math.floor((MAX_CONTEXT - picked) / 2));
  // 창을 **끌지 않고 민다.** 한쪽 끝에 걸리면 그냥 잘라 버리는 게 아니라 반대쪽을
  // 더 가져온다 — 문단 맨 끝을 끌었을 때 예산의 절반만 쓰던 자리다(실측 303/600).
  let end = Math.min(text.length, at + picked + half);
  const start = Math.max(0, Math.min(at - half, end - MAX_CONTEXT));
  end = Math.min(text.length, Math.max(end, start + MAX_CONTEXT));
  // 잘라 붙인 글이라는 걸 모델이 알게 한다 — 끊긴 문장을 오타로 읽지 않도록.
  return (
    (start > 0 ? "… " : "") +
    text.slice(start, end).trim() +
    (end < text.length ? " …" : "")
  );
}

/** 근거 — **두 층을 갈라 보여준다.**
 *
 *   이 화면의 교재 원문   그 설명을 만들 때 쓴 바로 그 조각. 주 근거다
 *   다른 자리            같은 개념이 또 있는 곳. 더 볼 곳이다
 *
 * 섞어 놓으면 "교재 기준으로 답한 것"과 "비슷한 걸 찾아 준 것"이 같은 무게로
 * 읽힌다. 근거가 아예 없을 때도 그렇다고 말한다 — 안 그러면 AI가 아는 대로
 * 답한 것과 교재를 읽고 답한 것이 화면에서 구별되지 않는다.
 */
function Grounds({
  grounded,
  page,
  sources,
}: {
  grounded: boolean;
  page: string | null;
  sources: AskSource[];
}) {
  return (
    <div className="mt-3 border-t border-border-primary pt-3">
      <p className="mb-1.5 text-[0.7rem] font-bold text-text-tertiary">
        이 설명의 근거
      </p>

      {grounded ? (
        <p className="flex items-start gap-1.5 text-[0.75rem] leading-snug text-text-secondary">
          <BookOpenTextIcon className="mt-0.5 shrink-0 text-[0.85rem] text-accent" />
          <span>
            <span className="font-semibold text-text-primary">
              이 화면의 교재 원문
            </span>
            {page && ` · ${page}`}
          </span>
        </p>
      ) : (
        <p className="text-[0.75rem] leading-snug text-text-tertiary">
          교재에서 관련 대목을 찾지 못해 일반 지식으로 답했어요.
        </p>
      )}

      {sources.length > 0 && (
        <>
          <p className="mt-2.5 mb-1.5 text-[0.7rem] font-bold text-text-tertiary">
            같은 개념이 여기에도 있어요
          </p>
          <ul className="space-y-1.5">
            {sources.map((s) => (
              <li key={`${s.documentId}-${s.concept}`} className="flex gap-1.5">
                <span className="mt-px shrink-0 text-[0.8rem]">
                  {/* 어느 책인지가 근거의 절반이다. 도서관 책이면 그렇다고
                      말한다 — 내 자료에서 나온 것과 무게가 다르다. */}
                  {s.shared ? (
                    <BooksIcon className="text-text-tertiary" />
                  ) : (
                    <FileTextIcon className="text-text-tertiary" />
                  )}
                </span>
                <span className="min-w-0 text-[0.75rem] leading-snug text-text-secondary">
                  <span className="font-semibold text-text-primary">
                    {s.concept}
                  </span>
                  {" · "}
                  {s.filename}
                  {s.topicTitle && ` · ${s.topicTitle}`}
                  {s.page && ` · ${s.page}`}
                  <span className="text-text-tertiary"> ({s.similarity})</span>
                </span>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}

export function AskPopover({
  docId,
  sectionId,
  containerRef,
}: {
  docId: string;
  sectionId: string;
  containerRef: React.RefObject<HTMLElement | null>;
}) {
  const [anchor, setAnchor] = useState<Anchor | null>(null);
  const [selection, setSelection] = useState("");
  const [context, setContext] = useState("");
  // 열렸나. 퀵메뉴만 뜬 상태(false)와 답 말풍선(true)을 가른다.
  const [open, setOpen] = useState(false);
  const [turns, setTurns] = useState<AskTurn[]>([]);
  // 근거는 **첫 답의 것을 지킨다**(아래 onSuccess). 그래서 답과 따로 들고 있다.
  const [ground, setGround] = useState<{
    grounded: boolean;
    page: string | null;
    sources: AskSource[];
  } | null>(null);
  const [followUp, setFollowUp] = useState("");
  const boxRef = useRef<HTMLDivElement>(null);
  const pos = usePlacement(anchor, boxRef, open);

  const ask = useMutation({
    mutationFn: (question?: string) =>
      askAboutSelection({
        docId,
        sectionId,
        selection,
        context,
        question,
        history: turns,
      }),
    onSuccess: (data, question) => {
      setTurns((prev) => [
        ...prev,
        ...(question ? [{ role: "user" as const, content: question }] : []),
        { role: "assistant" as const, content: data.answer },
      ]);
      // 근거는 **첫 답의 것을 지킨다.** 이어묻기마다 갈아치우면 "이 설명이 어느
      // 교재에서 왔나"가 대화 도중에 바뀌어 보인다.
      setGround(
        (prev) =>
          prev ?? {
            grounded: data.grounded,
            page: data.page,
            sources: data.sources,
          },
      );
    },
  });

  // `ask` 객체는 렌더마다 새로 만들어진다. 그대로 의존성에 넣으면 document
  // 리스너를 렌더마다 떼었다 붙인다 — `reset`만 뽑아 쓴다(이건 안 바뀐다).
  const { reset } = ask;

  const close = useCallback(() => {
    setAnchor(null);
    setOpen(false);
    setTurns([]);
    setGround(null);
    setFollowUp("");
    reset();
  }, [reset]);

  // 드래그가 끝나는 순간에만 본다. `selectionchange`로 보면 끄는 도중에도
  // 계속 떠서 글자를 가린다.
  useEffect(() => {
    const onUp = () => {
      // 말풍선 안에서 드래그한 건 새 질문이 아니다(답을 긁어 복사하는 중).
      if (boxRef.current && document.activeElement === boxRef.current) return;
      const sel = window.getSelection();
      if (!sel || sel.isCollapsed || sel.rangeCount === 0) {
        if (!open) setAnchor(null);
        return;
      }
      const text = sel.toString().trim();
      if (text.length < MIN_SELECTION || text.length > MAX_SELECTION) return;

      const range = sel.getRangeAt(0);
      const host = containerRef.current;
      if (!host || !host.contains(range.commonAncestorContainer)) return;
      // 말풍선 안에서 끈 것도 거른다.
      if (boxRef.current?.contains(range.commonAncestorContainer)) return;

      const node =
        range.commonAncestorContainer.nodeType === Node.ELEMENT_NODE
          ? (range.commonAncestorContainer as Element)
          : range.commonAncestorContainer.parentElement;
      if (node?.closest("[data-no-ask]")) return;

      const rect = range.getBoundingClientRect();
      if (rect.width === 0 && rect.height === 0) return;

      setSelection(text);
      setContext(contextOf(range));
      setTurns([]);
      setGround(null);
      reset();
      setOpen(false);
      setAnchor({
        top: rect.top,
        bottom: rect.bottom,
        left: rect.left,
        right: rect.right,
      });
    };

    document.addEventListener("mouseup", onUp);
    return () => document.removeEventListener("mouseup", onUp);
  }, [containerRef, open, reset]);

  // 바깥을 누르거나 Esc면 닫는다.
  useEffect(() => {
    if (!anchor) return;
    const onDown = (e: MouseEvent) => {
      if (!boxRef.current?.contains(e.target as Node)) close();
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") close();
    };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [anchor, close]);

  if (!anchor) return null;

  // 자리를 재기 전에는 화면 밖에 그린다. `useLayoutEffect`가 그리기 **전에**
  // 자리를 잡으므로 깜빡이지 않는다 — 대신 0,0에 한 번 찍히는 걸 막는다.
  const at = {
    left: pos?.left ?? -9999,
    top: pos?.top ?? -9999,
  };

  // 퀵메뉴 — 끌어 놓으면 이것만 뜬다. 누르기 전엔 서버를 안 부른다.
  if (!open) {
    return (
      <div ref={boxRef} style={at} className="fixed z-50">
        <button
          type="button"
          onMouseDown={(e) => e.preventDefault()}
          onClick={() => {
            setOpen(true);
            ask.mutate(undefined);
          }}
          className="flex items-center gap-1.5 rounded-full bg-primary px-4 py-2 text-[0.82rem] font-bold text-white shadow-lg transition-transform hover:scale-105"
        >
          <SparkleIcon weight="fill" className="text-[0.95rem]" />
          알아보기
        </button>
      </div>
    );
  }

  const answering = ask.isPending;

  return (
    <div
      ref={boxRef}
      style={at}
      className="fixed z-50 flex max-h-[calc(100vh-1.5rem)] w-[400px] max-w-[calc(100vw-1.5rem)] flex-col overflow-hidden rounded-2xl border border-border-primary bg-white shadow-2xl"
    >
      <div className="flex items-start gap-2 border-b border-border-primary bg-bg-secondary px-4 py-2.5">
        <SparkleIcon
          weight="fill"
          className="mt-0.5 shrink-0 text-[0.9rem] text-accent"
        />
        <p className="min-w-0 flex-1 truncate text-[0.82rem] font-bold text-text-primary">
          {selection}
        </p>
        <button
          type="button"
          onClick={close}
          aria-label="닫기"
          className="shrink-0 text-text-tertiary transition-colors hover:text-text-primary"
        >
          <XIcon />
        </button>
      </div>

      <div className="max-h-[45vh] overflow-y-auto px-4 py-3">
        {turns.map((t, i) =>
          t.role === "user" ? (
            <p
              key={i}
              className="mb-2 ml-auto w-fit max-w-[85%] rounded-xl rounded-br-[4px] bg-accent/10 px-3 py-2 text-[0.83rem] text-text-primary"
            >
              {t.content}
            </p>
          ) : (
            <p
              key={i}
              className="mb-3 whitespace-pre-line text-[0.87rem] leading-relaxed text-text-primary"
            >
              {t.content}
            </p>
          ),
        )}

        {answering && (
          <p className="flex items-center gap-2 py-1 text-[0.85rem] text-text-tertiary">
            <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-border-primary border-t-accent" />
            교재에서 찾아보는 중…
          </p>
        )}
        {ask.isError && (
          <p className="py-1 text-[0.85rem] text-red-600">
            설명을 만들지 못했어요. 잠시 후 다시 시도해 주세요.
          </p>
        )}

        {!answering && ground && (
          <Grounds
            grounded={ground.grounded}
            page={ground.page}
            sources={ground.sources}
          />
        )}
      </div>

      {/* 이어묻기 — 첫 답이 온 뒤에만 연다. 답도 없는데 입력창부터 보이면
          그냥 채팅창이 하나 더 생긴 것이다. */}
      {turns.length > 0 && (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            const q = followUp.trim();
            if (!q || answering) return;
            setFollowUp("");
            ask.mutate(q);
          }}
          className="flex items-center gap-2 border-t border-border-primary p-2.5"
        >
          <input
            value={followUp}
            onChange={(e) => setFollowUp(e.target.value)}
            placeholder="이어서 물어보기…"
            className="min-w-0 flex-1 rounded-full border border-border-primary bg-bg-secondary px-3.5 py-2 text-[0.83rem] text-text-primary outline-none transition-colors placeholder:text-text-tertiary focus:border-accent focus:bg-white"
          />
          <button
            type="submit"
            disabled={!followUp.trim() || answering}
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-accent text-white transition-transform hover:scale-105 disabled:opacity-40 disabled:hover:scale-100"
          >
            <PaperPlaneRightIcon weight="fill" className="text-[0.85rem]" />
          </button>
        </form>
      )}
    </div>
  );
}
