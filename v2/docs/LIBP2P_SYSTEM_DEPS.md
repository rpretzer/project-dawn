# Libp2p System Dependencies

## Required System Libraries

To fully install libp2p, you need system development libraries:

### Fedora/RHEL/CentOS

```bash
sudo dnf install gmp-devel
```

### Debian/Ubuntu

```bash
sudo apt-get install libgmp-dev
```

### macOS

```bash
brew install gmp
```

## Installation After System Dependencies

Once system dependencies are installed:

```bash
# Install fastecdsa (requires gmp)
pip install fastecdsa==2.3.2

# Verify libp2p works
python -c "import libp2p; print('✓ libp2p available')"
```

## Current Status

**System Dependencies**: ⚠️ **Not Installed** (requires sudo)  
**fastecdsa**: ⚠️ **Cannot Build** (needs gmp-devel)  
**libp2p**: ⚠️ **Partially Installed** (missing fastecdsa)

## Workaround

Until system dependencies are installed:

1. **Continue using WebSocket transport** (fully functional)
2. **Install system deps when possible** (requires admin access)
3. **Use Docker/container** (can install system deps in container)

## Verification

Check what's missing:

```bash
python -c "import libp2p" 2>&1 | grep -i fastecdsa
```

If you see "No module named 'fastecdsa'", install system dependencies and fastecdsa.
