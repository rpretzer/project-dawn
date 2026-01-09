# Libp2p Migration Decision Document

**Date**: 2026-01-08  
**Updated**: 2026-01-08  
**Status**: **IN PROGRESS** - Implementation being completed

## Decision

**Libp2p migration (Phase 3 Option A) is being implemented.**

The current custom WebSocket-based P2P implementation is:
- ✅ Fully functional
- ✅ Well-tested
- ✅ Production-ready
- ✅ Meets all current requirements

## Rationale

### Why Defer?

1. **Current Implementation Works**
   - Custom WebSocket transport is stable and reliable
   - Peer discovery (mDNS, Gossip, DHT) is implemented and working
   - No immediate need for Libp2p features

2. **Libp2p Implementation Challenges**
   - py-libp2p library may not be mature/available
   - Significant refactoring required
   - Migration effort vs. benefit unclear

3. **Feature Flag Protection**
   - Libp2p code is disabled by default (`LIBP2P_ENABLED=false`)
   - Clear error messages prevent accidental use
   - Code preserved for future consideration

### When to Revisit?

Consider Libp2p migration if:
- Need for automatic NAT traversal becomes critical
- Multi-transport support (QUIC, etc.) is required
- Interoperability with IPFS/Ethereum networks is needed
- Current implementation becomes a maintenance burden
- py-libp2p or alternative library becomes mature and stable

## Current State

### What Exists

1. **Placeholder Implementation**
   - `p2p/libp2p_transport.py` - Transport layer structure
   - `p2p/libp2p_node.py` - Node implementation structure
   - `p2p/libp2p_config.py` - Configuration system
   - All marked as incomplete with clear comments

2. **Feature Flag**
   - `LIBP2P_ENABLED` environment variable
   - Default: `false` (disabled)
   - Clear error messages when attempted

3. **Documentation**
   - Migration plan documented
   - Implementation guide available
   - Decision rationale recorded

### What's Missing

1. **Actual Libp2p Library Integration**
   - No py-libp2p installation
   - No actual Libp2p API calls
   - Placeholder implementations only

2. **Tests**
   - No tests for Libp2p (can't test placeholders)
   - Would need library integration first

## Options Going Forward

### Option A: Keep as Future Work (RECOMMENDED)
- ✅ Preserve code structure
- ✅ Keep feature flag disabled
- ✅ Document as "future work"
- ✅ Revisit when needed

**Action**: No changes needed, current state is acceptable

### Option B: Remove Libp2p Code
- Remove `p2p/libp2p_*.py` files
- Remove from `p2p/__init__.py` exports
- Clean up documentation references

**Pros**: Cleaner codebase, less confusion  
**Cons**: Lose migration path, would need to recreate later

### Option C: Complete Implementation
- Research and install Libp2p library
- Complete placeholder implementations
- Add tests
- Enable by default

**Pros**: Full Libp2p support  
**Cons**: Significant effort, unclear benefit

## Recommendation

**Keep Option A** - Preserve code as future work with clear documentation.

The placeholder code:
- Doesn't interfere with current functionality (disabled by default)
- Provides a migration path if needed later
- Is clearly marked as incomplete
- Has proper error handling

## Implementation Notes

### Using Libp2p (If Enabled Later)

1. **Enable Feature Flag**:
   ```bash
   export LIBP2P_ENABLED=true
   ```

2. **Install Library**:
   ```bash
   pip install py-libp2p
   # Or use libp2p-js bridge, or libp2p-rs FFI
   ```

3. **Complete Implementation**:
   - Replace placeholders in `libp2p_transport.py`
   - Implement actual Libp2p API calls
   - Add tests
   - Update documentation

### Current Usage

**Do NOT use Libp2p in production** - It will fail with clear error messages.

Use the standard P2P implementation:
```python
from p2p import P2PNode

node = P2PNode(
    identity=identity,
    address="ws://localhost:8000",
    enable_encryption=True,
)
```

## Conclusion

Libp2p migration is **being implemented**. The implementation uses py-libp2p library and provides a working Libp2p transport layer. The code is enabled via `LIBP2P_ENABLED=true` environment variable.

**Status**: 🚧 **In Progress** - Implementation complete, testing needed

## Implementation Status

### Completed
- ✅ Libp2p host creation
- ✅ Peer connection handling
- ✅ Stream management
- ✅ Message sending/receiving
- ✅ Bootstrap peer connection
- ✅ Integration with existing P2P node

### Testing Needed
- ⚠️ Multi-node network testing
- ⚠️ Peer discovery integration
- ⚠️ NAT traversal verification
- ⚠️ Performance benchmarking
