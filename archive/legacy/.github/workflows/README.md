# GitHub Actions Workflows

This directory contains CI/CD workflows for Project Dawn V2.

## Workflows

### `test.yml`
Runs the test suite on push and pull requests.

**Triggers**:
- Push to `main` or `develop` branches
- Pull requests to `main` or `develop` branches

**Actions**:
- Tests on Python 3.11 and 3.12
- Runs all test files
- Verifies imports

### `build-and-sign.yml`
Builds and signs releases with GPG.

**Triggers**:
- Release creation
- Manual workflow dispatch

**Actions**:
- Builds Python sidecar (if applicable)
- Generates SHA-256 checksums
- Signs checksum file with GPG
- Uploads artifacts

## Required Secrets

### For `build-and-sign.yml`:

1. **`GPG_PRIVATE_KEY`**
   - Your GPG private key (ASCII-armored)
   - Export with: `gpg --armor --export-secret-keys YOUR_KEY_ID`
   - Add to GitHub Secrets

2. **`GPG_PASSPHRASE`**
   - Passphrase for your GPG key
   - Add to GitHub Secrets

## Setup Instructions

1. **Generate GPG Key** (if not already done):
   ```bash
   gpg --full-generate-key
   ```

2. **Export Private Key**:
   ```bash
   gpg --armor --export-secret-keys YOUR_KEY_ID > private_key.asc
   ```

3. **Add to GitHub Secrets**:
   - Go to repository Settings → Secrets and variables → Actions
   - Add `GPG_PRIVATE_KEY` with contents of `private_key.asc`
   - Add `GPG_PASSPHRASE` with your passphrase

4. **Create Release**:
   - Go to Releases → Create a new release
   - Tag version (e.g., `v0.1.0`)
   - Workflow will automatically run

## Verification

After a release is created, you can verify the signature:

```bash
# Download artifacts
# Import public key
gpg --import public_key.asc

# Verify signature
gpg --verify CHECKSUM.txt.sig CHECKSUM.txt
```

## Troubleshooting

- **GPG signing fails**: Check that secrets are set correctly
- **Checksum generation fails**: Ensure `dist/` directory exists or adjust path
- **Workflow doesn't trigger**: Check that release is created (not draft)
