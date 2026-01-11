#!/bin/bash
# Build Tauri application

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
TAURI_DIR="$PROJECT_DIR/src-tauri"

echo "Building Project Dawn Tauri Application..."

# Check if Rust is installed
if ! command -v cargo &> /dev/null; then
    echo "Error: Rust/Cargo not found. Please install Rust: https://rustup.rs/"
    exit 1
fi

# Check if Tauri CLI is installed
if ! command -v tauri &> /dev/null; then
    echo "Installing Tauri CLI..."
    cargo install tauri-cli
fi

# Build Python sidecar first (optional, for production)
if [ "$1" != "--skip-sidecar" ]; then
    echo "Building Python sidecar..."
    cd "$PROJECT_DIR"
    python scripts/build_python_sidecar.py || {
        echo "Warning: Sidecar build failed, continuing with development mode..."
    }
fi

# Build Tauri application
echo "Building Tauri application..."
cd "$PROJECT_DIR"
node scripts/tauri-build.js

echo ""
echo "✓ Build complete!"
echo "Output: $TAURI_DIR/target/release/bundle/"
