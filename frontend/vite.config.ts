/// <reference types="vitest/config" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  // `assay dashboard` serves the built app from inside the Python package, from disk,
  // so one larger bundle is fine.
  build: {
    outDir: "../src/assay/dashboard_static",
    emptyOutDir: true,
    chunkSizeWarningLimit: 1024,
  },
  server: {
    // The FastAPI backend from `assay dashboard` serves the API during development.
    proxy: { "/api": "http://127.0.0.1:8000" },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/setupTests.ts"],
  },
});
