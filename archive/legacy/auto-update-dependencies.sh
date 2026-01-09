#!/bin/bash
# Automated dependency update script for cron/scheduled execution
# This script can be run daily/weekly via cron

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_SCRIPT="$SCRIPT_DIR/dependency-updater.py"
CONFIG_FILE="$SCRIPT_DIR/dependency-updater.config.json"
LOG_FILE="$SCRIPT_DIR/dependency-updates.log"
REPORT_DIR="$SCRIPT_DIR/dependency-reports"

# Create report directory if it doesn't exist
mkdir -p "$REPORT_DIR"

# Generate timestamp
TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")
REPORT_FILE="$REPORT_DIR/dependency-report-$TIMESTAMP.json"

echo "=========================================" >> "$LOG_FILE"
echo "Dependency Update Run: $(date)" >> "$LOG_FILE"
echo "=========================================" >> "$LOG_FILE"

# Run scan and generate report
python3 "$PYTHON_SCRIPT" --config "$CONFIG_FILE" --report "$REPORT_FILE" >> "$LOG_FILE" 2>&1

# Check if there are outdated dependencies
OUTDATED_COUNT=$(python3 -c "
import json
import sys
try:
    with open('$REPORT_FILE') as f:
        data = json.load(f)
        outdated = sum(1 for d in data['dependencies'] if d.get('update_available', False))
        print(outdated)
except:
    print(0)
")

if [ "$OUTDATED_COUNT" -gt 0 ]; then
    echo "Found $OUTDATED_COUNT outdated dependencies" >> "$LOG_FILE"
    
    # Option 1: Auto-update (uncomment to enable)
    # echo "Auto-updating dependencies..." >> "$LOG_FILE"
    # python3 "$PYTHON_SCRIPT" --config "$CONFIG_FILE" --update >> "$LOG_FILE" 2>&1
    
    # Option 2: Just log (current default)
    echo "Run './update-dependencies.sh update' to update dependencies" >> "$LOG_FILE"
else
    echo "All dependencies are up to date!" >> "$LOG_FILE"
fi

echo "" >> "$LOG_FILE"

# Keep only last 30 reports
cd "$REPORT_DIR" && ls -t dependency-report-*.json | tail -n +31 | xargs -r rm

echo "Report saved to: $REPORT_FILE"
echo "Log saved to: $LOG_FILE"

