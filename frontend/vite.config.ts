import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const proxy = {
  "/api": {
    target: process.env.CLEARLEDGER_API_URL || "http://127.0.0.1:8010",
    rewrite: (p: string) => p.replace(/^\/api/, ""),
  },
};

export default defineConfig(() => {
  const publicApi = process.env.VITE_API_BASE_URL;
  if (publicApi) {
    const origin = new URL(publicApi);
    const render =
      origin.protocol === "https:" &&
      origin.hostname.endsWith(".onrender.com") &&
      !origin.port;
    const loopback =
      origin.protocol === "http:" && origin.hostname === "127.0.0.1";
    if (origin.origin !== publicApi || (!render && !loopback))
      throw new Error(
        "VITE_API_BASE_URL must be an exact Render HTTPS or loopback test origin",
      );
  }
  return {
    plugins: [react()],
    server: {
      host: "127.0.0.1",
      port: 5173,
      strictPort: true,
      // Windows editors/scripts may briefly truncate a file before rewriting it.
      // Wait for a stable write before Vite invalidates and transforms modules.
      watch: {
        awaitWriteFinish: { stabilityThreshold: 200, pollInterval: 25 },
      },
      proxy,
    },
    preview: { host: "127.0.0.1", port: 4173, strictPort: true, proxy },
  };
});
