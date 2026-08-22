import { execFileSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(__dirname, "..");
const COMPOSE_FILE = path.join(REPO_ROOT, "docker-compose.yml");

export default async function globalTeardown(): Promise<void> {
  execFileSync("docker", ["compose", "-f", COMPOSE_FILE, "down", "-v"], {
    cwd: REPO_ROOT,
    stdio: "inherit",
  });
}
