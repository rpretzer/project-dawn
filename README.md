# Project Dawn

Project Dawn is a decentralized, multi-agent system built on the Model Context Protocol (MCP). It runs a Python P2P node with MCP agents and a web UI, and can be bundled into a Tauri desktop app with a Python sidecar.

## Core Components

- **Python node**: P2P networking + MCP server/clients + agents.
- **Frontend**: Local web UI served by the Python node.
- **Tauri app**: Desktop shell that launches the Python sidecar and reads local state for the UI.

## Data Storage

All sovereign data is stored under a single root directory. You can override it with:

```
PROJECT_DAWN_DATA_ROOT=/path/to/data
```

Default (no override): `./data` when running directly, or the OS app data dir when running via Tauri.

## Quick Start (Python)

```bash
pip install -r requirements.txt
python server_p2p.py
```

- WebSocket: `ws://localhost:8000`
- UI: `http://localhost:8080`

## Tauri Development

```bash
npm run tauri:dev
```

## Tauri Build

```bash
npm run build:sidecar
npm run tauri:build
```

## Tests

```bash
pytest --ignore=archive/legacy/tests -q
```

## Environment Variables

- `PROJECT_DAWN_DATA_ROOT`: override data root path for all Python modules and the Tauri shell.
- `LIBP2P_ENABLED=true`: enable libp2p transport (optional).

## LLM (Ollama)

The UI includes a local LLM picker for Ollama. It stores config at:
`<data-root>/vault/llm_config.json`.

Defaults:
- Endpoint: `http://localhost:11434`
- Model: unset (choose one via the picker)
