# Project Dawn - Dependency Management

This directory contains an automated dependency update system specifically configured for Project Dawn.

## Quick Start

```bash
# Scan for outdated dependencies
./update-dependencies.sh scan

# Preview what would be updated (safe)
./update-dependencies.sh dry-run

# Update all outdated dependencies
./update-dependencies.sh update

# Generate detailed JSON report
./update-dependencies.sh report
```

## Current Status

The system monitors **25 Python dependencies** in `requirements.txt`. As of the last scan, **23 dependencies** have updates available.

## Files

- `dependency-updater.py` - Main Python script for dependency management
- `dependency-updater.config.json` - Configuration (scoped to this project)
- `update-dependencies.sh` - Convenience wrapper script
- `auto-update-dependencies.sh` - Automated cron-ready script
- `DEPENDENCY_UPDATER_README.md` - Full documentation

## Configuration

The system is configured to:
- ✅ Update minor and patch versions automatically
- ❌ Skip major version updates (requires manual review)
- ✅ Monitor all packages in `requirements.txt`

## Automated Updates

To set up automated daily checks:

```bash
# Add to crontab
crontab -e

# Add this line for daily checks at 2 AM
0 2 * * * cd /home/rpretzer/project-dawn && ./auto-update-dependencies.sh
```

Reports and logs will be saved in:
- `dependency-reports/` - JSON reports with timestamps
- `dependency-updates.log` - Update history log

## Best Practices

1. **Always test first**: Run `./update-dependencies.sh dry-run` before updating
2. **Review changes**: Check `git diff requirements.txt` after updates
3. **Test your code**: Run your test suite after dependency updates
4. **Commit updates**: Version control your dependency changes

## Example Workflow

```bash
# 1. Check what's outdated
./update-dependencies.sh scan

# 2. Preview updates
./update-dependencies.sh dry-run

# 3. Update dependencies
./update-dependencies.sh update

# 4. Review changes
git diff requirements.txt

# 5. Test your application
python -m pytest  # or your test command

# 6. Commit if everything works
git add requirements.txt
git commit -m "Update dependencies"
```

