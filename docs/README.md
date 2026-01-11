# Documentation

This project keeps documentation intentionally lean. If a doc isn’t listed here, it’s considered outdated and has been removed.

## Architecture Snapshot

- **Python core**: P2P node + MCP agents + crypto in the repo root.
- **Frontend**: Static UI in `frontend/` served by the Python node.
- **Tauri shell**: `src-tauri/` launches the Python sidecar and reads state from the data root.

## Data Root

All persistent state lives under a single root directory.

- Default: `./data` when running via Python.
- Tauri: OS app data directory by default.
- Override: set `PROJECT_DAWN_DATA_ROOT` to force a specific path.

Directory layout:

```
<data-root>/
  vault/
  mesh/
  outbox/
```

## Build & Run

- Python: `python server_p2p.py`
- Tauri dev: `npm run tauri:dev`
- Tauri build: `npm run build:sidecar && npm run tauri:build`

## Tests

```bash
pytest --ignore=archive/legacy/tests -q
```

## LLM Picker

The UI supports local Ollama models. Configuration is stored at:
`<data-root>/vault/llm_config.json`.
