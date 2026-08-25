// Deliberately separate from vite.config.ts, which wraps
// @lovable.dev/vite-tanstack-config (TanStack Start/SSR plugins that a plain
// unit-test run doesn't need and that aren't safe to reconfigure by hand —
// see the warning at the top of that file).
import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "jsdom",
    include: ["src/**/*.test.{ts,tsx}"],
  },
});
