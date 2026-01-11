# Build & Integrity Scripts

This directory contains build helpers and integrity tooling for the Python sidecar.

## Sidecar Build

The Tauri build uses `scripts/build_python_sidecar.py` to package `server_p2p.py` into a standalone binary and generate a SHA-256 checksum.

```bash
python scripts/build_python_sidecar.py
```

## Integrity

- `generate_checksum.py` — generate SHA-256 checksums
- `sign_release.py` — sign checksums with GPG
- `verify_integrity.py` — verify checksums and signatures

Example:

```bash
python scripts/generate_checksum.py dist/ CHECKSUM.txt
python scripts/sign_release.py CHECKSUM.txt
python scripts/verify_integrity.py dist/ public_key.asc
```

## Notes

- Keep private keys out of the repo.
- Use `PROJECT_DAWN_DATA_ROOT` to control runtime data location.
