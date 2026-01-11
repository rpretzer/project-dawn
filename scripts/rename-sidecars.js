#!/usr/bin/env node
import fs from "fs";
import path from "path";
import { execSync } from "child_process";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const root = path.resolve(__dirname, "..");
const sidecarDir = path.join(root, "src-tauri", "sidecar");
const binDir = path.join(root, "src-tauri", "bin");
const baseName = "project-dawn-server";

let target = process.env.TAURI_TARGET || process.env.TARGET || "";
if (!target) {
  try {
    const output = execSync("rustc -vV", { stdio: ["ignore", "pipe", "ignore"] })
      .toString();
    const match = output.match(/^host:\s+(.+)$/m);
    if (match) {
      target = match[1].trim();
    }
  } catch {
    // No rustc available; fall back to platform hint only.
  }
}
const platformHint = target.toLowerCase() || process.platform;

function ensureDir(dir) {
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
}

function fileExists(filePath) {
  try {
    return fs.statSync(filePath).isFile();
  } catch {
    return false;
  }
}

function copyIfMissing(src, dest) {
  if (!fileExists(src)) {
    return false;
  }
  if (!fileExists(dest)) {
    fs.copyFileSync(src, dest);
    return true;
  }
  return false;
}

function main() {
  ensureDir(sidecarDir);
  ensureDir(binDir);

  const unixPath = path.join(sidecarDir, baseName);
  const winPath = path.join(sidecarDir, `${baseName}.exe`);

  if (platformHint.includes("windows") || platformHint.includes("mingw")) {
    const copied = copyIfMissing(unixPath, winPath);
    if (copied) {
      console.log(`Copied sidecar to ${winPath}`);
    }
  } else {
    const copied = copyIfMissing(winPath, unixPath);
    if (copied) {
      console.log(`Copied sidecar to ${unixPath}`);
    }
  }

  if (target) {
    const targetSuffix = platformHint.includes("windows") || platformHint.includes("mingw")
      ? `${baseName}-${target}.exe`
      : `${baseName}-${target}`;
    const targetPath = path.join(binDir, targetSuffix);
    const sourcePath = platformHint.includes("windows") || platformHint.includes("mingw")
      ? winPath
      : unixPath;
    if (copyIfMissing(sourcePath, targetPath)) {
      console.log(`Prepared Tauri sidecar binary ${targetPath}`);
    }
  }
}

main();
