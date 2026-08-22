/**
 * Brings up the real docker-compose.yaml stack before the suite runs — same
 * approach as backend/tests_integration/conftest.py, mirrored here since
 * this suite drives real browsers against real containers instead of
 * running the app in-process.
 */
import { execFileSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(__dirname, "..");
const COMPOSE_FILE = path.join(REPO_ROOT, "docker-compose.yml");

function compose(...args: string[]): void {
  execFileSync("docker", ["compose", "-f", COMPOSE_FILE, ...args], {
    cwd: REPO_ROOT,
    stdio: "inherit",
  });
}

async function waitUntilReachable(url: string, timeoutMs = 30000): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  let lastError: unknown;
  while (Date.now() < deadline) {
    try {
      const res = await fetch(url);
      if (res.ok) return;
      lastError = new Error(`${url} responded with ${res.status}`);
    } catch (err) {
      lastError = err;
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  throw new Error(`${url} did not become reachable: ${String(lastError)}`);
}

export default async function globalSetup(): Promise<void> {
  // Clean slate: a stray container from earlier manual testing on the same
  // port, or a leftover volume, would otherwise make this suite flaky.
  compose("down", "-v");
  compose("up", "-d", "--wait", "--wait-timeout", "60");
  await waitUntilReachable("http://localhost:8000/");
}
