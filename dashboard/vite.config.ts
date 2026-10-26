import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Built output is served by the existing FastAPI app (app/main.py mounts
// app/static at /static), so the base path and outDir both need to line up
// with that: assets resolve from /static/dashboard/..., and the build lands
// directly in app/static/dashboard so no copy step is needed.
export default defineConfig({
  plugins: [react()],
  base: "/static/dashboard/",
  build: {
    outDir: "../app/static/dashboard",
    emptyOutDir: true,
  },
  server: {
    // `npm run dev` proxies API calls straight to the FastAPI backend
    // (`uv run python -m uvicorn app.main:app --reload`) so there's no need
    // to run a built copy just to iterate on the UI.
    proxy: {
      "/api": "http://localhost:8000",
    },
  },
});
