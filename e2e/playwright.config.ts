import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  fullyParallel: false,
  retries: 0,
  workers: 1,
  // "list" for readable CI logs, "html" (not auto-opened) so CI has a
  // report worth uploading as an artifact on failure.
  reporter: [["list"], ["html", { open: "never" }]],
  globalSetup: "./global-setup.ts",
  globalTeardown: "./global-teardown.ts",
  // The candidate's canvas edit only reaches the interviewer through the
  // frontend's polling fallback (POLL_INTERVAL = 4s, plus up to 800ms of
  // autosave debounce on the candidate's side) — there's no live push
  // (see frontend/src/lib/realtime.ts), so assertions need real headroom.
  expect: { timeout: 10000 },
  use: {
    baseURL: "http://localhost:8000",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
});
