#!/usr/bin/env bash
# 로컬 엔진(오프라인 이중구조) 기동 — llama-server(:8080, EXAONE 1.2B) + 어댑터(:8600).
# 모델/바이너리는 온디바이스 MVP 워크트리 것을 재사용한다(수백 MB 중복 방지).
# 함정 노하우: libgomp.so.1이 시스템에 없어 바이너리 폴더의 것을 LD_LIBRARY_PATH로.
set -euo pipefail

ONDEVICE_MVP="${ONDEVICE_MVP:-$HOME/metalearn-ondevice/ondevice}"
LLAMA_DIR="$ONDEVICE_MVP/llama/llama-b9935"
MODEL="$ONDEVICE_MVP/models/EXAONE-4.0-1.2B-Q4_K_M.gguf"
HERE="$(cd "$(dirname "$0")" && pwd)"

if ! curl -s -o /dev/null http://127.0.0.1:8080/health; then
  echo "[run_local] llama-server 기동 (:8080)"
  (cd "$LLAMA_DIR" && LD_LIBRARY_PATH=. ./llama-server -m "$MODEL" --port 8080 -c 4096 -t "$(nproc)" --no-webui >/tmp/llama-server.log 2>&1 &)
  for _ in $(seq 1 30); do
    curl -s -o /dev/null http://127.0.0.1:8080/health && break
    sleep 1
  done
else
  echo "[run_local] llama-server 이미 떠 있음"
fi

echo "[run_local] 어댑터 기동 (:8600)"
exec python3 "$HERE/adapter.py"
