# Installing Authentication Dependencies

## Required: Install bcrypt for Secure Password Hashing

The authentication system uses bcrypt for secure password hashing. To enable it, install bcrypt:

```bash
pip install bcrypt>=4.0.0
```

Or install all requirements:

```bash
pip install -r requirements.txt
```

## Note

The system will work without bcrypt (using SHA256 fallback), but this is **not secure for production**. Always use bcrypt in production environments.

## Verification

After installation, verify bcrypt is working:

```python
python3 -c "import bcrypt; print('bcrypt installed successfully')"
```

You should no longer see "bcrypt not available" warnings when starting the server.

