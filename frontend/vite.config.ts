import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";
import { version } from "./package.json";

export default defineConfig(({ mode }) => {
  // Root .env and process environment share APP_BASE_PATH with Compose.
  const env = loadEnv(mode, "..", "APP_");
  const basePath = (env.APP_BASE_PATH ?? "/tradebridge").replace(/\/+$/, "");
  if (!/^(\/[A-Za-z0-9_-]+)+$/.test(basePath)) {
    throw new Error("APP_BASE_PATH must be a non-root path such as /tradebridge, using letters, digits, _ or -.");
  }
  return {
    base: `${basePath}/`,
    define: { __APP_VERSION__: JSON.stringify(version) },
    plugins: [react()],
    server: { host: "127.0.0.1", port: 5173 }
  };
});
