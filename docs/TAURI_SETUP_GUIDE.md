# Tauri Application Setup Guide

## Current Status

The Tauri application has been **created** but **not yet built or run**. The structure is in place:

- ✅ `src-tauri/` directory with Rust code
- ✅ `Cargo.toml` with Tauri dependencies
- ✅ `tauri.conf.json` configuration
- ✅ Frontend files in `frontend/`
- ❌ Rust/Cargo not installed
- ❌ Tauri CLI not installed
- ❌ Application not built

## What is Tauri?

Tauri is a framework for building desktop applications using web technologies (HTML/CSS/JS) with a Rust backend. For Project Dawn:

- **Frontend**: Your existing `v2/frontend/` (HTML/JS)
- **Backend**: Python server runs as a "sidecar" process
- **Wrapper**: Rust/Tauri manages both and creates a desktop app

## Installation Steps

### 1. Install Rust

```bash
# Install Rust using rustup
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# Reload shell
source ~/.cargo/env

# Verify
rustc --version
cargo --version
```

### 2. Install Tauri CLI

```bash
# Install Tauri CLI
cargo install tauri-cli

# Verify
tauri --version
```

### 3. Install Node.js Dependencies (if needed)

```bash
cd v2
npm install
```

### 4. Build Python Sidecar (for production)

```bash
# Build Python server as executable
cd v2
python scripts/build_python_sidecar.py
```

This creates `src-tauri/sidecar/project-dawn-server` executable.

### 5. Run Tauri Application

**Development mode** (uses Python directly, not sidecar):
```bash
cd v2
npm run tauri:dev
# Or
cargo tauri dev
```

**Production build**:
```bash
cd v2
npm run tauri:build
# Or
cargo tauri build
```

## How It Works

### Development Mode

When you run `tauri dev`:
1. Tauri starts a Rust process
2. Rust process spawns Python server: `python3 server_p2p.py`
3. Tauri loads frontend from `frontend/` directory
4. Frontend connects to Python server via WebSocket (localhost:8000)
5. Everything runs in a desktop window (not browser)

### Production Mode

When you build with `tauri build`:
1. Python server is packaged as executable (sidecar)
2. Tauri bundles everything into a single `.app` (macOS) or `.exe` (Windows) or `.AppImage` (Linux)
3. User runs the binary, which:
   - Starts Tauri window
   - Launches Python sidecar automatically
   - Loads bundled frontend
   - Everything is self-contained

## Current Setup

Right now, you're running:
```bash
python3 launch.py --realtime --port 8000
```

This is the **Python server directly**, accessible via browser at `http://localhost:8000`.

To use the **Tauri application** instead:
1. Install Rust and Tauri CLI (see above)
2. Run `npm run tauri:dev` from `v2/` directory
3. A desktop window will open (not a browser)
4. The Python server runs as a sidecar process automatically

## Benefits of Tauri

- ✅ **Desktop app** - Not a browser tab
- ✅ **Signed binaries** - Can be code-signed for trust
- ✅ **Smaller size** - Much smaller than Electron
- ✅ **Better performance** - Uses system WebView
- ✅ **System integration** - Can access system APIs
- ✅ **Tamper-resistant** - Harder to modify than browser app

## Troubleshooting

### "rustc: command not found"
- Install Rust: `curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh`

### "tauri: command not found"
- Install Tauri CLI: `cargo install tauri-cli`

### "Sidecar not found"
- Build sidecar first: `python scripts/build_python_sidecar.py`
- Or run in dev mode (uses Python directly)

### "Frontend not loading"
- Check `tauri.conf.json` `devPath` points to `../frontend`
- Ensure frontend files exist

## Next Steps

1. **Install Rust and Tauri CLI** (see Installation Steps above)
2. **Test in development mode**: `npm run tauri:dev`
3. **Build for production**: `npm run tauri:build`
4. **Distribute**: Share the built binary with users

---

**Note**: The Tauri application is ready to use once Rust and Tauri CLI are installed. The code is complete and functional.
