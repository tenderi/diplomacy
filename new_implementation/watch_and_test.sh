#!/bin/bash
# Watch for changes in new_implementation and run tests automatically
# Requires: inotify-tools (install with: sudo pacman -S inotify-tools)

WATCH_DIR="$(dirname "$0")"
OUTPUT_FILE="$WATCH_DIR/test_output.txt"
VENV_DIR="$WATCH_DIR/venv"

# Activate venv if it exists
if [ -d "$VENV_DIR" ]; then
    source "$VENV_DIR/bin/activate"
fi

echo "Watching $WATCH_DIR for changes. Running tests on change. Output: $OUTPUT_FILE"



while true; do
    inotifywait -r -e modify,create,delete,move "$WATCH_DIR" --exclude '(__pycache__|\.pyc|\.log|venv|\.pytest_cache)'
    clear
    echo "[Watcher] Change detected. Running tests..."
    pytest "$WATCH_DIR/src/" -v > "$OUTPUT_FILE" 2>&1
    echo "[Watcher] Test run complete. Output saved to $OUTPUT_FILE."
    echo "--- Last 20 lines of output ---"
    tail -20 "$OUTPUT_FILE"
    echo "[Watcher] Waiting for next change..."
done 