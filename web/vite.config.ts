import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The API base is a build-time value, not a runtime fetch of some config.json. The SPA is served from
// CloudFront and the API from a Lambda Function URL — two hostnames, deliberately, per the phase 5
// IMPLEMENTATION doc 4.1. CloudFront does NOT front the Function URL: the streaming path cost a whole
// verification spike to establish and an untested intermediary in front of it is the one place in this
// phase where a wrong call is expensive.
//
// Left empty, the app talks to a same-origin `/api` proxy, which is what `npm run dev` provides below.
export default defineConfig(({ mode }) => ({
  plugins: [react()],
  build: {
    // Named so the deploy sync can set a long cache lifetime on hashed assets and a short one on
    // index.html, without a rule that has to know Vite's internals.
    outDir: "dist",
    sourcemap: mode !== "production",
  },
  server: {
    // Dev only. The deployed app never proxies — it calls the Function URL directly, which is why the
    // Function URL carries the CloudFront domain in its CORS allow-list.
    proxy: {
      "/api": {
        target: process.env.MYCELIUM_API ?? "http://127.0.0.1:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test-setup.ts"],
  },
}));
