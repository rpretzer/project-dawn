#!/bin/bash
# Install Libp2p with all dependencies
# This script handles the installation process including system dependencies

set -e

echo "Installing Libp2p for Project Dawn V2..."
echo ""

# Detect OS
if [ -f /etc/fedora-release ] || [ -f /etc/redhat-release ]; then
    OS="fedora"
    PKG_MGR="dnf"
    PKG_NAME="gmp-devel"
elif [ -f /etc/debian_version ]; then
    OS="debian"
    PKG_MGR="apt-get"
    PKG_NAME="libgmp-dev"
elif [[ "$OSTYPE" == "darwin"* ]]; then
    OS="macos"
    PKG_MGR="brew"
    PKG_NAME="gmp"
else
    OS="unknown"
    echo "Warning: Unknown OS, cannot auto-install system dependencies"
fi

# Check if system dependencies are needed
echo "Checking for system dependencies..."

if command -v python3 -c "import fastecdsa" &>/dev/null; then
    echo "✓ fastecdsa already available"
    NEED_SYSTEM_DEPS=false
else
    echo "⚠ fastecdsa not found, will need system dependencies"
    NEED_SYSTEM_DEPS=true
fi

# Install system dependencies if needed
if [ "$NEED_SYSTEM_DEPS" = true ] && [ "$OS" != "unknown" ]; then
    echo ""
    echo "System dependencies are required for fastecdsa:"
    echo "  $PKG_MGR install $PKG_NAME"
    echo ""
    read -p "Install system dependencies now? (requires sudo) [y/N]: " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        if [ "$OS" = "macos" ]; then
            $PKG_MGR install $PKG_NAME
        else
            sudo $PKG_MGR install -y $PKG_NAME
        fi
        echo "✓ System dependencies installed"
    else
        echo "⚠ Skipping system dependencies. fastecdsa installation will fail."
        echo "  You can install them manually later and run: pip install fastecdsa==2.3.2"
    fi
fi

# Install coincurve from GitHub (bypasses PyPI metadata issue)
echo ""
echo "Installing coincurve from GitHub..."
pip install git+https://github.com/ofek/coincurve.git || {
    echo "⚠ coincurve installation failed, trying PyPI..."
    pip install coincurve==21.0.0 || {
        echo "✗ coincurve installation failed"
        exit 1
    }
}

# Install libp2p
echo ""
echo "Installing libp2p..."
pip install libp2p --no-deps || {
    echo "⚠ Direct installation failed, trying with dependencies..."
    pip install libp2p || {
        echo "✗ libp2p installation failed"
        exit 1
    }
}

# Install dependencies
echo ""
echo "Installing libp2p dependencies..."
pip install \
    multiaddr==0.0.11 \
    base58 \
    aioquic \
    grpcio \
    lru-dict \
    mypy-protobuf \
    "protobuf>=4.25.0,<7.0.0" \
    py-multihash \
    pycryptodome \
    pynacl \
    rpcudp \
    trio-typing \
    noiseprotocol \
    "zeroconf>=0.147.0,<0.148.0" \
    miniupnpc \
    || echo "⚠ Some dependencies failed to install"

# Install fastecdsa if system deps are available
echo ""
if [ "$NEED_SYSTEM_DEPS" = false ] || command -v python3 -c "import fastecdsa" &>/dev/null; then
    echo "fastecdsa already available, skipping..."
else
    echo "Installing fastecdsa (may fail if system deps missing)..."
    pip install fastecdsa==2.3.2 || {
        echo "⚠ fastecdsa installation failed"
        echo "  Install system dependencies and try: pip install fastecdsa==2.3.2"
    }
fi

# Verify installation
echo ""
echo "Verifying installation..."
python3 -c "
import sys
sys.path.insert(0, '.')
try:
    from p2p.libp2p_impl import PY_LIBP2P_AVAILABLE
    if PY_LIBP2P_AVAILABLE:
        print('✓ Libp2p implementation available')
    else:
        print('⚠ Libp2p implementation not fully available')
        print('  Check error messages above')
except Exception as e:
    print(f'✗ Verification failed: {e}')
" || echo "⚠ Verification had issues"

echo ""
echo "Installation complete!"
echo ""
echo "To use Libp2p:"
echo "  export LIBP2P_ENABLED=true"
echo "  python server_p2p.py  # or use Libp2pP2PNode in code"
