import { defineConfig } from "vitest/config";

// Test settings; the app build stays in vite.config.ts.
export default defineConfig({
  test: {
    // The pet-pack tests (src/mascot/packs.test.ts) list the asset files with
    // import.meta.glob, which runs when the test file is transformed: a cached
    // transform would keep checking an old file list and miss new clips.
    fsModuleCache: false,
  },
});
