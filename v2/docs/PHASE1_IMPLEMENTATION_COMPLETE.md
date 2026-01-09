# Phase 1: The Sovereign Shell (Tauri + Sidecar) - Implementation Complete

## Overview

Phase 1 of the Tauri Migration & Enhanced Distribution Plan has been successfully implemented. This phase migrates Project Dawn from a browser-based application to a signed, tamper-resistant desktop binary using Tauri.

## Implementation Summary

### Tauri Project Structure Created

1. **`src-tauri/Cargo.toml`**
   - Rust project configuration
   - Tauri dependencies (v1.5)
   - Sidecar support enabled

2. **`src-tauri/src/main.rs`**
   - Main Rust application entry point
   - Sidecar process management
   - Health monitoring
   - Development/production mode detection

3. **`src-tauri/tauri.conf.json`**
   - Application configuration
   - Window settings
   - Bundle configuration
   - Sidecar resource paths

4. **`src-tauri/build.rs`**
   - Build script for Tauri

### Build Scripts Created

1. **`scripts/build_python_sidecar.py`**
   - Packages Python server as standalone executable
   - Supports PyInstaller and Nuitka
   - Bundles all dependencies and assets
   - Creates executable for Tauri sidecar

2. **`scripts/build_tauri.sh`**
   - Complete build script for Tauri application
   - Builds sidecar first, then Tauri
   - Handles errors gracefully

3. **`scripts/create_tauri_icons.sh`**
   - Generates Tauri icons from source image
   - Creates all required icon sizes

### Configuration Files

1. **`package.json`**
   - npm scripts for Tauri development and building
   - Commands: `tauri:dev`, `tauri:build`, `build:sidecar`

2. **`src-tauri/.gitignore`**
   - Ignores Rust build artifacts
   - Ignores sidecar executables

## Architecture

### Development Mode

When running `npm run tauri:dev`:
- Tauri launches and serves frontend from `../frontend`
- Python server runs directly via `python3 server_p2p.py`
- WebSocket connection: `ws://localhost:8000`
- HTTP server: `http://localhost:8080`
- Hot-reload enabled

### Production Mode

When building with `npm run tauri:build`:
- Python server packaged as `project-dawn-server` executable
- Executable bundled in Tauri resources
- Tauri launches sidecar automatically
- Frontend bundled with application
- Single `.exe/.app/.deb` binary

### Sidecar Process Management

The Rust application:
1. **Detects mode**: Checks if sidecar executable exists
2. **Launches process**: 
   - Development: `python3 server_p2p.py`
   - Production: `./sidecar/project-dawn-server`
3. **Monitors health**: Periodic TCP connection checks
4. **Handles cleanup**: Terminates sidecar on app exit

## Usage

### Development

```bash
# Install Tauri CLI (first time only)
cargo install tauri-cli

# Run in development mode
npm run tauri:dev

# Or directly
cd src-tauri
cargo tauri dev
```

### Building for Production

```bash
# Build Python sidecar
npm run build:sidecar

# Build Tauri application
npm run tauri:build

# Or build everything
npm run build:all
```

### Creating Icons

```bash
# Create icons from source image
./scripts/create_tauri_icons.sh icon.png
```

## Frontend Adaptations

**No changes required!** The frontend works as-is because:
- Tauri WebView supports standard WebSocket API
- Frontend connects to `localhost:8000` (same as before)
- All existing JavaScript code works unchanged
- No browser-specific APIs that need Tauri alternatives

## File Structure

```
v2/
├── src-tauri/              # Tauri Rust application
│   ├── src/
│   │   └── main.rs        # Main Rust code
│   ├── icons/             # Application icons
│   ├── Cargo.toml         # Rust dependencies
│   ├── tauri.conf.json    # Tauri configuration
│   └── build.rs           # Build script
├── scripts/
│   ├── build_python_sidecar.py  # Python packaging
│   ├── build_tauri.sh            # Tauri build script
│   └── create_tauri_icons.sh     # Icon generation
├── frontend/               # Frontend (unchanged)
├── server_p2p.py          # Python server (unchanged)
└── package.json           # npm scripts
```

## Key Features

### Automatic Sidecar Management
- Sidecar starts automatically with Tauri
- Health monitoring every 5 seconds
- Automatic restart on failure (can be added)
- Clean shutdown on app exit

### Development/Production Detection
- Automatically detects if sidecar executable exists
- Falls back to Python in development
- Uses bundled executable in production

### Error Handling
- Graceful fallback to Python if sidecar missing
- Error logging for debugging
- Process cleanup on exit

## Prerequisites

### For Development
- Rust (https://rustup.rs/)
- Tauri CLI: `cargo install tauri-cli`
- Python 3.11+
- Node.js (optional, for npm scripts)

### For Building
- All development prerequisites
- PyInstaller or Nuitka: `pip install pyinstaller`
- ImageMagick (for icon generation, optional)

## Build Output

After building, you'll find:
- **Windows**: `src-tauri/target/release/bundle/msi/project-dawn_0.1.0_x64_en-US.msi`
- **macOS**: `src-tauri/target/release/bundle/macos/Project Dawn.app`
- **Linux**: `src-tauri/target/release/bundle/deb/project-dawn_0.1.0_amd64.deb`

## Next Steps

1. **Test Development Mode**
   ```bash
   npm run tauri:dev
   ```

2. **Create Icons**
   - Create or find a 1024x1024 icon
   - Run: `./scripts/create_tauri_icons.sh icon.png`

3. **Build Sidecar**
   ```bash
   npm run build:sidecar
   ```

4. **Build Application**
   ```bash
   npm run tauri:build
   ```

5. **Test Production Build**
   - Run the generated executable
   - Verify sidecar starts automatically
   - Test WebSocket connection

## Troubleshooting

### Sidecar won't start
- Check Python is installed: `python3 --version`
- Check `server_p2p.py` exists in project root
- Check Tauri console for error messages

### Build fails
- Ensure Rust is installed: `rustc --version`
- Install Tauri CLI: `cargo install tauri-cli`
- Check `Cargo.toml` dependencies

### Frontend not loading
- Check `tauri.conf.json` `devPath` points to `../frontend`
- Ensure frontend files exist
- Check browser console in Tauri dev tools

### Sidecar executable not found
- Build sidecar first: `npm run build:sidecar`
- Check `src-tauri/sidecar/` directory exists
- Verify executable permissions

## Status

✅ **Phase 1 Complete** - Tauri project structure created and sidecar management implemented.

## Files Created

- `v2/src-tauri/Cargo.toml` - Rust project config
- `v2/src-tauri/src/main.rs` - Main Rust application
- `v2/src-tauri/tauri.conf.json` - Tauri configuration
- `v2/src-tauri/build.rs` - Build script
- `v2/src-tauri/.gitignore` - Git ignore rules
- `v2/src-tauri/README.md` - Documentation
- `v2/scripts/build_python_sidecar.py` - Python packaging script
- `v2/scripts/build_tauri.sh` - Tauri build script
- `v2/scripts/create_tauri_icons.sh` - Icon generation script
- `v2/package.json` - npm scripts
