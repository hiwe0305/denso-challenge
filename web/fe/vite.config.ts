/// <reference types="vitest" />
import { fileURLToPath } from "node:url";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// The MSW handlers read mock/demo-17-11/ at the repo root (DESIGN.md Appendix C),
// so the dev server must be allowed to serve files three levels up.
const repoRoot = fileURLToPath(new URL("../..", import.meta.url));

export default defineConfig({
  plugins: [react()],
  // In mock mode MSW answers /api before the request leaves the browser; with
  // VITE_API_MODE=real the request reaches this proxy and `python -m web.api`.
  server: {
    fs: { allow: [repoRoot] },
    proxy: { "/api": "http://127.0.0.1:8000" },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
  },
});
