#!/usr/bin/env bash
# Build release packages: .deb and AppImage into src-tauri/target/release/bundle/.
#
#   scripts/package.sh            both
#   scripts/package.sh deb        only the .deb
#
# Uses the same clean environment as run.sh (VS Code's snap leaks GTK paths).
# AppImage bundling downloads Tauri's linuxdeploy helpers on first use
# (build time only; the app itself never touches the network).
set -euo pipefail
cd "$(dirname "$0")/.."

for v in $(env | grep -oE '^(SNAP[A-Z_]*|GTK_PATH|GTK_EXE_PREFIX|GTK_IM_MODULE_FILE|GIO_MODULE_DIR|GDK_PIXBUF_MODULE_FILE|GDK_PIXBUF_MODULEDIR|GSETTINGS_SCHEMA_DIR|LOCPATH)='); do
  unset "${v%=}"
done
[[ -n "${XDG_DATA_DIRS_VSCODE_SNAP_ORIG:-}" ]] && export XDG_DATA_DIRS="$XDG_DATA_DIRS_VSCODE_SNAP_ORIG"
export PATH="$HOME/.cargo/bin:$PATH"

BUNDLES="${1:-deb,appimage}"
(cd src-tauri && cargo test --lib --quiet)
npx tauri build --bundles "$BUNDLES"
echo
find src-tauri/target/release/bundle -maxdepth 2 -type f \( -name '*.deb' -o -name '*.AppImage' \) -printf '%p  (%s bytes)\n'
