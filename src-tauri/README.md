# Project Dawn Tauri Shell

This directory contains the Tauri (Rust) desktop wrapper for Project Dawn.

## Structure

- `src/main.rs` — Tauri entry point
- `tauri.conf.json` — bundle configuration
- `sidecar/` — bundled Python executable
- `bin/` — Tauri external sidecar target builds

## Development

```bash
npm run tauri:dev
```

## Production Build

```bash
npm run build:sidecar
npm run tauri:build
```

## Data Root

The Tauri shell resolves a data root as follows:

1. `PROJECT_DAWN_DATA_ROOT` (if set)
2. OS app data directory

The data root is passed to the sidecar via `PROJECT_DAWN_DATA_ROOT` and used by UI reads (`get_manifest`, `get_peers`, `get_feed`, `get_resource_state`).

## Sidecar

The Python sidecar (`project-dawn-server`) is started with:
- integrity verification (checksum)
- health checks
- automatic shutdown on app close
