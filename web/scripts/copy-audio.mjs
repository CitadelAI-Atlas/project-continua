#!/usr/bin/env node
/**
 * Copy data/wavs/* into web/public/audio/* before the Next.js build.
 * Run automatically by the npm "prebuild" script.
 */
import { cpSync, existsSync, mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = resolve(__dirname, "..", "..");
const SRC = resolve(REPO_ROOT, "data", "wavs");
const DST = resolve(__dirname, "..", "public", "audio");

if (!existsSync(SRC)) {
  console.error(`[copy-audio] source not found: ${SRC}`);
  process.exit(1);
}

mkdirSync(DST, { recursive: true });

cpSync(SRC, DST, {
  recursive: true,
  // Skip non-WAV files (no JSON, no .DS_Store, etc.)
  filter: (src) => {
    const stat = src.endsWith(".wav") || !src.includes(".");
    return stat;
  },
});

console.log(`[copy-audio] copied ${SRC} -> ${DST}`);
