# Project Dawn Tauri Application

This directory contains the Tauri (Rust) wrapper for Project Dawn.

## Structure

- `src/main.rs` - Main Rust application entry point
- `Cargo.toml` - Rust dependencies and configuration
- `tauri.conf.json` - Tauri application configuration
- `build.rs` - Build script
- `sidecar/` - Python server executable (built separately)

## Development

### Prerequisites

1. **Rust**: Install from https://rustup.rs/
2. **Tauri CLI**: `cargo install tauri-cli`
3. **Python**: For sidecar development mode
4. **Node.js**: For frontend (optional, Tauri can serve directly)

### Running in Development

```bash
# From project root
npm run tauri:dev

# Or directly with cargo
cd src-tauri
cargo tauri dev
```

In development mode, Tauri will:
- Run the Python server directly (not as sidecar)
- Serve the frontend from `../frontend`
- Enable hot-reload

### Building for Production

```bash
# Build Python sidecar first
npm run build:sidecar

# Build Tauri application
npm run tauri:build

# Or build everything
npm run build:all
```

## Sidecar Process

The Python server (`server_p2p.py`) runs as a sidecar process:

- **Development**: Runs Python directly via `python3 server_p2p.py`
- **Production**: Runs bundled executable from `sidecar/project-dawn-server`

The sidecar:
- Starts automatically when Tauri launches
- Runs on `localhost:8000` (WebSocket) and `localhost:8080` (HTTP)
- Is monitored for health
- Is terminated when Tauri closes

## Configuration

### Port Configuration

Default ports:
- WebSocket: 8000
- HTTP: 8080

These can be changed in `server_p2p.py` and the frontend configuration.

### Window Configuration

Edit `tauri.conf.json` to customize:
- Window size and title
- Icon paths
- Bundle settings
- Permissions

## Troubleshooting

### Sidecar won't start

1. Check Python is installed: `python3 --version`
2. Check server script exists: `ls server_p2p.py`
3. Check logs in Tauri console

### Build fails

1. Ensure Rust is installed: `rustc --version`
2. Ensure Tauri CLI is installed: `cargo install tauri-cli`
3. Check `Cargo.toml` dependencies are correct

### Frontend not loading

1. Check `tauri.conf.json` `devPath` points to frontend directory
2. Ensure frontend files exist in `../frontend`
3. Check browser console for errors
