import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    host: true, // 컨테이너 외부(호스트)에서 접근 가능하게
    port: 5173,
  },
});
