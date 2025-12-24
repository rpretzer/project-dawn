#!/bin/bash
# Convenience script for running dependency updates

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_SCRIPT="$SCRIPT_DIR/dependency-updater.py"
CONFIG_FILE="$SCRIPT_DIR/dependency-updater.config.json"

# Default action: scan
ACTION="${1:-scan}"

case "$ACTION" in
    scan)
        python3 "$PYTHON_SCRIPT" --config "$CONFIG_FILE" --scan
        ;;
    update)
        python3 "$PYTHON_SCRIPT" --config "$CONFIG_FILE" --update
        ;;
    dry-run)
        python3 "$PYTHON_SCRIPT" --config "$CONFIG_FILE" --update --dry-run
        ;;
    report)
        python3 "$PYTHON_SCRIPT" --config "$CONFIG_FILE" --report dependency-report.json
        ;;
    *)
        echo "Usage: $0 [scan|update|dry-run|report]"
        echo ""
        echo "Commands:"
        echo "  scan      - Scan for outdated dependencies (default)"
        echo "  update    - Update all outdated dependencies"
        echo "  dry-run   - Show what would be updated without making changes"
        echo "  report    - Generate JSON report of dependencies"
        exit 1
        ;;
esac

