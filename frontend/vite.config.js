import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    // During local development the backend runs separately on port 8000.
    // This forwards every /api request to it, so the frontend code can always
    // call "/api/chat", locally and on Vercel.
    proxy: {
      "/api": "http://localhost:8000",
    },
  },
});
