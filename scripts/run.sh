#!/usr/bin/env bash
# Build the frontend + binary and launch it with a clean GTK environment.
#
#   scripts/run.sh            debug build, attached to this terminal
#   scripts/run.sh -d         detached: keeps running after the terminal closes
#   scripts/run.sh --stop     quit a running instance
#   PROFILE=release ...       optimized build
#
# Why: the VS Code snap exports GTK_PATH, GIO_MODULE_DIR, LOCPATH, etc. pointing
# into /snap/code; a host-linked WebKitGTK app inheriting them crashes with
# "undefined symbol: __libc_pthread_init". We also call cargo directly because
# `tauri dev` needs inotify watches, which large editors often exhaust.
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ "${1:-}" == "--stop" ]]; then
  pkill -x deskbuddy && echo "DeskBuddy stopped." || echo "DeskBuddy is not running."
  exit 0
fi

for v in $(env | grep -oE '^(SNAP[A-Z_]*|GTK_PATH|GTK_EXE_PREFIX|GTK_IM_MODULE_FILE|GIO_MODULE_DIR|GDK_PIXBUF_MODULE_FILE|GDK_PIXBUF_MODULEDIR|GSETTINGS_SCHEMA_DIR|LOCPATH)='); do
  unset "${v%=}"
done
[[ -n "${XDG_DATA_DIRS_VSCODE_SNAP_ORIG:-}" ]] && export XDG_DATA_DIRS="$XDG_DATA_DIRS_VSCODE_SNAP_ORIG"
[[ -n "${XDG_CONFIG_DIRS_VSCODE_SNAP_ORIG:-}" ]] && export XDG_CONFIG_DIRS="$XDG_CONFIG_DIRS_VSCODE_SNAP_ORIG"
export PATH="$HOME/.cargo/bin:$PATH"

PROFILE="${PROFILE:-debug}"
npm run build
if [[ "$PROFILE" == release ]]; then
  (cd src-tauri && cargo build --release --features tauri/custom-protocol)
else
  (cd src-tauri && cargo build --features tauri/custom-protocol)
fi
BIN="src-tauri/target/$PROFILE/deskbuddy"

if [[ "${1:-}" == "-d" ]]; then
  LOG="${XDG_STATE_HOME:-$HOME/.local/state}/deskbuddy/deskbuddy.log"
  mkdir -p "$(dirname "$LOG")"
  setsid nohup "$BIN" >"$LOG" 2>&1 </dev/null &
  echo "DeskBuddy running in the background (PID $!). Log: $LOG"
  echo "Quit from the mascot's right-click menu, or: scripts/run.sh --stop"
  exit 0
fi
exec "$BIN" "$@"
