#!/bin/zsh
set -euo pipefail

cd "$(dirname "$0")"

DATA_DIR="${1:-}"
PORT="8766"

if [[ ! -x ".venv/bin/python" ]]; then
  echo "Project environment is missing. From this folder, run: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
  read -r "?Press Return to close this window..."
  exit 1
fi

if [[ -z "$DATA_DIR" ]]; then
  DATA_DIR=$(osascript -e 'POSIX path of (choose folder with prompt "Select the data folder containing reference/ and the month folder")') || exit 1
fi

if [[ ! -d "$DATA_DIR/reference" ]]; then
  echo "Can't find a reference/ folder in: $DATA_DIR"
  echo "Select the parent data folder. It should contain reference/ and a month folder with bills.csv."
  read -r "?Press Return to close this window..."
  exit 1
fi

MONTH_LIST=$(find "$DATA_DIR" -mindepth 2 -maxdepth 2 -type f -name bills.csv -print | sed -E 's|.*/([^/]+)/bills\.csv$|\1|' | sort -u)
MONTH_COUNT=$(printf '%s\n' "$MONTH_LIST" | awk 'NF { n++ } END { print n+0 }')
if [[ "$MONTH_COUNT" -eq 0 ]]; then
  echo "No month folder containing bills.csv was found in: $DATA_DIR"
  read -r "?Press Return to close this window..."
  exit 1
elif [[ "$MONTH_COUNT" -eq 1 ]]; then
  MONTH="$MONTH_LIST"
else
  echo "More than one month is available:"
  print -r -- "$MONTH_LIST"
  while true; do
    read -r "MONTH?Type the month folder to review: "
    if printf '%s\n' "$MONTH_LIST" | grep -Fxq "$MONTH"; then break; fi
    echo "Choose one of the month names listed above."
  done
fi

RUN_ID=$(date '+%Y%m%d-%H%M%S')
OUT_DIR="out/demo-${MONTH}-${RUN_ID}"

if [[ -f "$DATA_DIR/$MONTH/paper-bills.pdf" ]] && ! command -v tesseract >/dev/null 2>&1; then
  echo "Tesseract is required to read paper bills. Install it with: brew install tesseract"
  read -r "?Press Return to close this window..."
  exit 1
fi

echo "Reviewing month $MONTH from: $DATA_DIR"
echo "This run will be saved separately at: $OUT_DIR"
.venv/bin/python -m billreview --data "$DATA_DIR" --month "$MONTH" --out "$OUT_DIR"

if lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Port $PORT is already in use. Close the earlier demo window, then try again."
  read -r "?Press Return to close this window..."
  exit 1
fi

echo
echo "Starting the local review page at http://127.0.0.1:$PORT"
.venv/bin/python -m billreview.review_server "$OUT_DIR" --port "$PORT" &
SERVER_PID=$!
trap 'kill "$SERVER_PID" 2>/dev/null || true' EXIT INT TERM

for _ in {1..30}; do
  if curl -fsS "http://127.0.0.1:$PORT/" >/dev/null; then
    open "http://127.0.0.1:$PORT/"
    echo "Browser opened. Keep this window open while you use the page. Press Control+C to stop the local server."
    wait "$SERVER_PID"
    exit 0
  fi
  sleep 0.2
done

echo "The review server did not start. Check whether port $PORT is already in use."
exit 1
