# Libp2p fastecdsa Workaround

## Problem

`fastecdsa` requires the `gmp-devel` system library which needs sudo to install. This blocks full Libp2p functionality.

## Current Status

- ✅ **GMP runtime library**: Installed (`gmp-6.3.0`)
- ❌ **GMP development headers**: Missing (`gmp-devel` package)
- ❌ **fastecdsa**: Cannot build without headers

## Solutions

### Solution 1: Install System Dependency (Requires Admin)

```bash
# Fedora/RHEL
sudo dnf install gmp-devel

# Then install fastecdsa
pip install fastecdsa==2.3.2
```

### Solution 2: Check if Headers Exist Elsewhere

Sometimes GMP headers might be in a non-standard location:

```bash
# Search for gmp.h
find /usr -name "gmp.h" 2>/dev/null

# If found, set include path
export C_INCLUDE_PATH=/path/to/gmp/include:$C_INCLUDE_PATH
pip install fastecdsa==2.3.2
```

### Solution 3: Use Pre-built Wheel (If Available)

Check if there's a pre-built wheel for your platform:

```bash
pip install fastecdsa==2.3.2 --only-binary :all:
```

### Solution 4: Alternative Implementation

If fastecdsa cannot be installed, consider:

1. **Use WebSocket transport** (current default, fully functional)
2. **Wait for system dependency installation**
3. **Use Docker/container** where system deps can be installed

## Why fastecdsa is Required

Libp2p uses fastecdsa for:
- ECDSA cryptography (secp256k1 curves)
- Key pair generation
- Digital signatures

This is a core security component and cannot be easily replaced.

## Verification

Check if gmp-devel is needed:

```bash
# Check if headers exist
ls /usr/include/gmp.h

# Check what provides them
rpm -q --whatprovides /usr/include/gmp.h

# Install if missing
sudo dnf install gmp-devel
```

## Recommendation

**For now**: Continue using WebSocket transport (fully functional)

**When ready**: Install system dependency and fastecdsa to enable Libp2p

The Libp2p implementation code is complete and ready - it just needs this one system dependency to be installed.
