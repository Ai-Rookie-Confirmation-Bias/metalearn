import type { ButtonHTMLAttributes } from "react";

// 재사용 디자인 시스템 컴포넌트 (예시)
export function Button(props: ButtonHTMLAttributes<HTMLButtonElement>) {
  return <button {...props} style={{ padding: "0.5rem 1rem", ...props.style }} />;
}
