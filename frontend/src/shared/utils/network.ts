// 네트워크 연결 상태 체크 (runtime/provider의 분기 판단에 사용)
export function isOnline(): boolean {
  return typeof navigator !== "undefined" ? navigator.onLine : true;
}
