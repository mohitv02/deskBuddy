import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { resolve } from "node:path";

// Two pages: the tiny mascot window (vanilla TS, no React) and the panel (React).
export default defineConfig({
  plugins: [react()],
  clearScreen: false,
  server: { port: 1420, strictPort: true, host: "127.0.0.1" },
  build: {
    target: "safari15",
    // WebKitGTK supports <link rel=modulepreload>; the polyfill would add the
    // bundle's only fetch() call.
    modulePreload: { polyfill: false },
    rollupOptions: {
      input: {
        mascot: resolve(__dirname, "index.html"),
        panel: resolve(__dirname, "panel.html"),
        fx: resolve(__dirname, "fx.html"),
      },
    },
  },
});
