import { fileURLToPath, URL } from "node:url";

import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  resolve: {
    // tsconfig의 "@/*" → "src/*" 별칭을 Vite에도 동일하게 적용
    // (Vite는 tsconfig paths를 자동으로 읽지 않음).
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  server: {
    host: true, // 컨테이너 외부(호스트)에서 접근 가능하게
    port: 5173,
  },
});
