import { Fragment, type ReactNode } from "react";

/**
 * 안 보이는 제어문자를 보이게 그리는 공용 렌더러.
 *
 * 원문 뷰어(1단계)와 정규화 프리뷰(2.5단계)가 **같은 기준**으로 그려야 한다.
 * 한쪽만 배지를 그리면 "여기선 보이는데 저기선 안 보인다"가 되어 어느 쪽이
 * 진실인지 알 수 없다.
 *
 * 실측: pilgi.pdf는 어절 사이가 U+0007(BEL)이라 그냥 그리면
 * "현대적인프로그래밍기술을"처럼 붙어 보인다 — 공백 소실과 증상이 같아서
 * 실물을 보여주지 않으면 원인을 못 가른다.
 *
 * 백엔드 quality.py의 _CONTROL_RE와 대상이 같다. 탭·개행·캐리지리턴은
 * 정상 서식이라 뺀다.
 */
export const CONTROL_RE = new RegExp(
  "([\u0000-\u0008\u000B\u000C\u000E-\u001F\u007F])",
);

export function isControlChar(part: string): boolean {
  return part.length === 1 && CONTROL_RE.test(part);
}

/**
 * 제어문자를 ␇ 배지로 바꿔 그린다.
 *
 * renderText로 일반 구간의 렌더링을 바깥에서 정할 수 있다 — 원문 뷰어는
 * 검색어 하이라이트를 얹어야 하고, 프리뷰는 그대로 그리면 된다.
 */
export function ControlText({
  text,
  renderText,
}: {
  text: string;
  renderText?: (part: string, index: number) => ReactNode;
}) {
  return (
    <>
      {text.split(CONTROL_RE).map((part, i) =>
        isControlChar(part) ? (
          <ControlBadge key={i} char={part} />
        ) : renderText ? (
          renderText(part, i)
        ) : (
          <Fragment key={i}>{part}</Fragment>
        ),
      )}
    </>
  );
}

function ControlBadge({ char }: { char: string }) {
  return (
    <span
      title={`U+${char.charCodeAt(0).toString(16).toUpperCase().padStart(4, "0")}`}
      className="mx-px rounded bg-red-100 px-0.5 text-[10px] font-bold text-red-700"
    >
      ␇
    </span>
  );
}
