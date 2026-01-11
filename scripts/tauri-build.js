#!/usr/bin/env node
import fs from "fs";
import path from "path";
import { execFileSync, spawnSync } from "child_process";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const root = path.resolve(__dirname, "..");

function appendEnvPath(env, key, value) {
  if (!value) {
    return;
  }
  env[key] = env[key] ? `${value}:${env[key]}` : value;
}

function ensureDir(dir) {
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
}

function ensureSymlink(target, linkPath) {
  try {
    if (fs.existsSync(linkPath)) {
      return;
    }
    fs.symlinkSync(target, linkPath);
  } catch (err) {
    console.warn(`Warning: failed to create symlink ${linkPath}: ${err.message}`);
  }
}

function prepareLinuxCompat(env) {
  const pkgConfigDir = path.join(root, "scripts", "pkgconfig");
  if (fs.existsSync(pkgConfigDir)) {
    appendEnvPath(env, "PKG_CONFIG_PATH", pkgConfigDir);
  }

  const libshimDir = path.join(root, "scripts", "libshim");
  const libPaths = ["/usr/lib64", "/usr/lib"];
  const webkit = libPaths.find((dir) =>
    fs.existsSync(path.join(dir, "libwebkit2gtk-4.1.so"))
  );
  const jsc = libPaths.find((dir) =>
    fs.existsSync(path.join(dir, "libjavascriptcoregtk-4.1.so"))
  );

  if (webkit || jsc) {
    ensureDir(libshimDir);
    if (webkit) {
      ensureSymlink(
        path.join(webkit, "libwebkit2gtk-4.1.so"),
        path.join(libshimDir, "libwebkit2gtk-4.0.so")
      );
    }
    if (jsc) {
      ensureSymlink(
        path.join(jsc, "libjavascriptcoregtk-4.1.so"),
        path.join(libshimDir, "libjavascriptcoregtk-4.0.so")
      );
    }
  }

  if (fs.existsSync(libshimDir)) {
    appendEnvPath(env, "LIBRARY_PATH", libshimDir);
    const flag = `-L native=${libshimDir}`;
    env.RUSTFLAGS = env.RUSTFLAGS ? `${flag} ${env.RUSTFLAGS}` : flag;
  }
}

const env = { ...process.env };
if (process.platform === "linux") {
  prepareLinuxCompat(env);
}

const renameScript = path.join(root, "scripts", "rename-sidecars.js");
execFileSync(process.execPath, [renameScript], { stdio: "inherit", env });

const tauriBin = path.join(
  root,
  "node_modules",
  ".bin",
  process.platform === "win32" ? "tauri.cmd" : "tauri"
);

if (!fs.existsSync(tauriBin)) {
  console.error("Tauri CLI not found. Run `npm install` first.");
  process.exit(1);
}

const result = spawnSync(tauriBin, ["build"], { stdio: "inherit", env });
process.exit(result.status ?? 1);
