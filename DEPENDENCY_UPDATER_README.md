# Automated Dependency Update System

A comprehensive system for automatically detecting and updating package dependencies across multiple package managers and projects.

## Features

- **Multi-Package Manager Support**: Works with npm, pip, pipenv, poetry, cargo, and go mod
- **Automatic Detection**: Auto-detects projects and their package managers
- **Code Reference Checking**: Identifies code files that reference dependencies
- **Dry Run Mode**: Preview changes before applying them
- **JSON Reports**: Generate detailed reports of all dependencies
- **Scheduled Updates**: Support for cron-based automated checking

## Installation

1. Make sure Python 3.6+ is installed
2. Install required Python packages (if needed):
   ```bash
   pip install packaging
   ```
3. Make scripts executable:
   ```bash
   chmod +x dependency-updater.py update-dependencies.sh auto-update-dependencies.sh
   ```

## Configuration

Edit `dependency-updater.config.json` to configure which projects to monitor:

```json
{
  "projects": [
    {
      "path": "/path/to/project",
      "package_managers": ["npm", "pip"],
      "auto_update": true,
      "update_major": false,
      "update_minor": true,
      "update_patch": true,
      "exclude_packages": []
    }
  ]
}
```

If no config file exists, the system will auto-detect projects in common locations.

## Usage

### Basic Commands

**Scan for outdated dependencies:**
```bash
./update-dependencies.sh scan
# or
python3 dependency-updater.py --scan
```

**Preview updates (dry run):**
```bash
./update-dependencies.sh dry-run
# or
python3 dependency-updater.py --update --dry-run
```

**Update all outdated dependencies:**
```bash
./update-dependencies.sh update
# or
python3 dependency-updater.py --update
```

**Generate JSON report:**
```bash
./update-dependencies.sh report
# or
python3 dependency-updater.py --report dependency-report.json
```

### Advanced Usage

**Update specific project:**
```python
python3 dependency-updater.py --config /path/to/custom-config.json --update
```

**Check code references:**
The system automatically checks for code references when updating dependencies. References are logged to help identify files that might need code changes.

## Automated Scheduling

### Cron Setup

To run automatic dependency checks daily:

```bash
# Edit crontab
crontab -e

# Add this line for daily checks at 2 AM
0 2 * * * /home/rpretzer/auto-update-dependencies.sh
```

### Weekly Updates

For weekly automated updates (be careful with this):

```bash
# Edit the auto-update-dependencies.sh file
# Uncomment the auto-update section
```

## Project Structure

```
.
├── dependency-updater.py          # Main Python script
├── dependency-updater.config.json # Configuration file
├── update-dependencies.sh         # Convenience wrapper script
├── auto-update-dependencies.sh    # Cron-ready automation script
├── dependency-reports/            # Generated reports (created automatically)
└── dependency-updates.log         # Update log file
```

## How It Works

1. **Detection**: Scans configured projects for package manager files (package.json, requirements.txt, etc.)
2. **Version Checking**: Queries package registries (npm, PyPI) for latest versions
3. **Comparison**: Compares current versions with latest available
4. **Update**: Updates dependency files with new versions
5. **Code Reference**: Scans codebase for import/require statements referencing updated packages

## Supported Package Managers

- **npm** (Node.js): Updates package.json
- **pip** (Python): Updates requirements.txt
- **pipenv**: Updates Pipfile (planned)
- **poetry**: Updates pyproject.toml (planned)
- **cargo** (Rust): Updates Cargo.toml (planned)
- **go mod** (Go): Updates go.mod (planned)

## Safety Features

- **Dry Run Mode**: Always test with `--dry-run` first
- **Version Pinning**: Respects existing version constraints (^, ~, ==, etc.)
- **Backup**: Consider backing up dependency files before bulk updates
- **Major Version Updates**: Disabled by default (set `update_major: true` to enable)

## Troubleshooting

**Issue: Script can't find packages**
- Ensure package managers (npm, pip) are installed and in PATH
- Check network connectivity for registry queries

**Issue: Updates not applying**
- Check file permissions on dependency files
- Verify package manager syntax in dependency files

**Issue: False positives for outdated packages**
- Some packages may have pre-release versions that are filtered out
- Check package registries manually if needed

## Best Practices

1. **Test First**: Always run with `--dry-run` before updating
2. **Review Changes**: Check git diff after updates
3. **Run Tests**: Test your application after dependency updates
4. **Incremental Updates**: Update dependencies in small batches
5. **Monitor Logs**: Check `dependency-updates.log` regularly

## Example Workflow

```bash
# 1. Scan for outdated dependencies
./update-dependencies.sh scan

# 2. Review what would be updated
./update-dependencies.sh dry-run

# 3. Generate a report
./update-dependencies.sh report

# 4. Update dependencies
./update-dependencies.sh update

# 5. Review changes
git diff package.json requirements.txt

# 6. Test your application
npm test
pytest

# 7. Commit if everything works
git add package.json requirements.txt
git commit -m "Update dependencies"
```

## License

This tool is provided as-is for dependency management automation.

