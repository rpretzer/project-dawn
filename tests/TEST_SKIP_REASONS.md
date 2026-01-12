# Test Skip Reasons Documentation

This document explains why certain tests are skipped and when they can be enabled.

## Transport Tests (`test_transport.py`)

### Skip Reasons:

1. **Socket Operations Not Permitted**:
   - **Location**: `test_transport.py:20`
   - **Reason**: Socket operations are not permitted in some test environments (e.g., CI/CD sandboxes)
   - **Fix**: Use mock sockets or skip in restricted environments only
   - **Status**: Acceptable skip in restricted environments

2. **WebSockets Library Not Available**:
   - **Location**: `test_transport.py:27, 85, 105`
   - **Reason**: `websockets` library is optional and may not be installed
   - **Fix**: Install `websockets` package: `pip install websockets`
   - **Status**: Should be installed in test environment

## Libp2p Tests (`test_libp2p.py`)

### Skip Reasons:

1. **Libp2p Not Enabled**:
   - **Location**: `test_libp2p.py:19, 34, 66, 106`
   - **Reason**: Libp2p is an optional transport and disabled by default
   - **Fix**: Set `LIBP2P_ENABLED=true` environment variable
   - **Status**: Acceptable skip (optional feature)

2. **py-libp2p Library Not Installed**:
   - **Location**: `test_libp2p.py:26, 38, 70, 110`
   - **Reason**: `py-libp2p` library is optional and may not be installed
   - **Fix**: Install `py-libp2p` package: `pip install libp2p` (if available)
   - **Status**: Acceptable skip (optional dependency)

3. **Library Issues**:
   - **Location**: `test_libp2p.py:98, 136`
   - **Reason**: Library API compatibility issues or bugs
   - **Fix**: Wait for library updates or use alternative implementation
   - **Status**: Acceptable skip (known library issues)

## Host Tests (`test_host.py`)

### Skip Reasons:

1. **WebSockets Library Not Available**:
   - **Location**: `test_host.py:70, 106`
   - **Reason**: `websockets` library is optional
   - **Fix**: Install `websockets` package
   - **Status**: Should be installed in test environment

## MCP Server Client Tests (`test_mcp_server_client.py`)

### Skip Reasons:

1. **WebSockets Library Not Available**:
   - **Location**: `test_mcp_server_client.py:136`
   - **Reason**: `websockets` library is optional
   - **Fix**: Install `websockets` package
   - **Status**: Should be installed in test environment

## Recommendations

### Should Fix:
- **WebSockets tests**: Add `websockets` to test dependencies in `requirements.txt` or `requirements-dev.txt`
- **Document skip reasons**: All skips should have clear comments explaining why

### Acceptable Skips:
- **Libp2p tests**: Optional feature, skip is acceptable
- **Socket operations in restricted environments**: Skip is acceptable in CI/CD sandboxes
- **Library compatibility issues**: Skip is acceptable until library is fixed

### Documentation:
- All skipped tests should have clear `pytest.skip()` messages explaining why
- Update this document when skip reasons change
- Review skipped tests periodically to see if they can be enabled
