# Changelog

All notable changes to this project are documented in this file.

## [0.1.1] - 2025-02-15
### Added
- Shared data root resolver with `PROJECT_DAWN_DATA_ROOT` override.
- Tauri data-root handoff to sidecar and UI state reads from app data dir.

### Changed
- Sidecar results are signed and include public key metadata.
- Transport and protocol stability improvements for async tests and JSON-RPC notifications.
- Documentation reset to match current architecture and build flow.

### Fixed
- Test reliability for websocket transport under restricted environments.
- Missing-import warnings for optional runtime dependencies.

## [0.1.0] - 2025-02-15
### Added
- Initial decentralized MCP-based multi-agent system with P2P networking.
- Tauri shell with sidecar integrity verification and resource monitoring.
- Proof-of-Logits compute, discovery, and reputation modules.
