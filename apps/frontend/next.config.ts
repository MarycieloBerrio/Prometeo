import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import type { NextConfig } from "next";

/**
 * The repo-root `.env` is the team's single settings file (shared with the API and docker
 * compose). Next.js only reads `.env*` from apps/frontend, so load the `PROMETEO_*` keys the
 * server needs (e.g. PROMETEO_API_URL) from the root file. Real environment variables win.
 * Only `PROMETEO_*` keys are read, so secrets such as ANTHROPIC_API_KEY never enter this process.
 */
function loadRepoRootEnv(): void {
  const repoRoot = path.join(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
  const file = path.join(repoRoot, ".env");
  if (!existsSync(file)) return;
  const values = new Map<string, string>();
  for (const line of readFileSync(file, "utf8").split(/\r?\n/)) {
    const match = /^\s*(PROMETEO_[A-Z0-9_]+)\s*=\s*(.*?)\s*$/.exec(line);
    if (match) values.set(match[1], match[2].replace(/^(["'])(.*)\1$/, "$2")); // last wins
  }
  for (const [key, value] of values) {
    if (process.env[key] === undefined) process.env[key] = value;
  }
}

loadRepoRootEnv();

const nextConfig: NextConfig = {
  cacheComponents: true,
  partialPrefetching: true,
};

export default nextConfig;
