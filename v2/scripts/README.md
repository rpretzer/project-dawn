# Release Signing and Verification Scripts

This directory contains scripts for Phase 2: Integrity & PGP Verification of the Tauri Migration plan.

## Scripts

### `generate_checksum.py`
Generates SHA-256 checksums for release files.

**Usage:**
```bash
# Generate checksum for a single file
python scripts/generate_checksum.py dist/project-dawn-server.exe

# Generate checksum for a directory
python scripts/generate_checksum.py dist/

# Specify output file
python scripts/generate_checksum.py dist/ CHECKSUM.txt
```

### `sign_release.py`
Signs release files with GPG/PGP.

**Prerequisites:**
- GPG installed and configured
- GPG key generated (see below)

**Usage:**
```bash
# Sign checksum file
python scripts/sign_release.py CHECKSUM.txt

# Sign with specific key
python scripts/sign_release.py CHECKSUM.txt YOUR_KEY_ID
```

**Output:**
- Creates `CHECKSUM.txt.sig` (or `RELEASE.sig`)

### `verify_integrity.py`
Verifies release integrity using checksums and PGP signatures.

**Usage:**
```bash
# Verify release directory
python scripts/verify_integrity.py dist/

# Verify with specific public key
python scripts/verify_integrity.py dist/ public_key.asc
```

## GPG Key Setup

### 1. Generate GPG Key

```bash
gpg --full-generate-key
```

Follow the prompts:
- Key type: RSA and RSA (default)
- Key size: 4096
- Expiration: Your choice (0 = no expiration)
- Name, Email, Comment: Your developer info
- Passphrase: Strong passphrase

### 2. Export Public Key

```bash
# Export in ASCII format
gpg --armor --export YOUR_KEY_ID > public_key.asc

# List your keys to find KEY_ID
gpg --list-keys
```

### 3. Hardcode Public Key in Application

The public key should be embedded in the application for runtime verification:

```python
# In application code
PUBLIC_KEY = """
-----BEGIN PGP PUBLIC KEY BLOCK-----
...
-----END PGP PUBLIC KEY BLOCK-----
"""
```

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Build and Sign Release

on:
  release:
    types: [created]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Build application
        run: |
          # Your build commands
          python scripts/generate_checksum.py dist/ CHECKSUM.txt
      
      - name: Sign release
        env:
          GPG_PRIVATE_KEY: ${{ secrets.GPG_PRIVATE_KEY }}
          GPG_PASSPHRASE: ${{ secrets.GPG_PASSPHRASE }}
        run: |
          echo "$GPG_PRIVATE_KEY" | gpg --import
          python scripts/sign_release.py CHECKSUM.txt
      
      - name: Upload artifacts
        uses: actions/upload-artifact@v3
        with:
          name: release
          path: |
            dist/
            CHECKSUM.txt
            CHECKSUM.txt.sig
```

## Release Process

1. **Build the application**
   ```bash
   # Build your application
   python build.py
   ```

2. **Generate checksums**
   ```bash
   python scripts/generate_checksum.py dist/ CHECKSUM.txt
   ```

3. **Sign the checksum file**
   ```bash
   python scripts/sign_release.py CHECKSUM.txt
   ```

4. **Verify before release**
   ```bash
   python scripts/verify_integrity.py dist/ public_key.asc
   ```

5. **Package release**
   - Include `CHECKSUM.txt`
   - Include `CHECKSUM.txt.sig` (or `RELEASE.sig`)
   - Include `public_key.asc` (for users to import)

## In-App Verification

The `verify_integrity.py` script can be integrated into the application for runtime verification:

```python
from scripts.verify_integrity import IntegrityVerifier
from pathlib import Path

# Hardcoded public key (embedded in application)
PUBLIC_KEY = Path(__file__).parent / "public_key.asc"

verifier = IntegrityVerifier(public_key_path=PUBLIC_KEY)
is_valid, messages = verifier.verify_release(Path("."))

if not is_valid:
    print("Integrity check failed! Refusing to run.")
    sys.exit(1)
```

## Security Notes

- **Never commit private keys** to the repository
- **Use secrets management** in CI/CD (GitHub Secrets, etc.)
- **Hardcode public key** in application for verification
- **Verify on startup** to prevent tampering
- **Refuse to run** if verification fails
