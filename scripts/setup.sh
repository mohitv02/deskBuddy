#!/usr/bin/env bash
# One-time setup to build DeskBuddy from source on a fresh Ubuntu 22.04.
#
#   scripts/setup.sh        install build tools + dependencies
#   scripts/run.sh          then build and launch (or scripts/package.sh deb)
#
# Installs: the GTK/WebKit dev packages (apt), Rust via rustup if cargo is
# missing, Node 22 via nvm if node is missing or older than 20.19 (Ubuntu's
# own nodejs is too old for Vite), then the npm packages.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "==> System packages (needs sudo)"
sudo apt update
sudo apt install -y build-essential curl pkg-config libssl-dev \
  libwebkit2gtk-4.1-dev libgtk-3-dev libayatana-appindicator3-dev librsvg2-dev libxdo-dev \
  pulseaudio-utils python3-pil

echo "==> Rust"
export PATH="$HOME/.cargo/bin:$PATH"
cargo_ok() {
  # Ubuntu's apt cargo (1.75) can't read Cargo.lock v4 or the 2024 edition.
  command -v cargo >/dev/null && [[ "$(cargo -V | awk '{print $2}' | cut -d. -f2)" -ge 85 ]]
}
if ! command -v rustup >/dev/null && ! cargo_ok; then
  curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
  export PATH="$HOME/.cargo/bin:$PATH"
else
  rustup update stable 2>/dev/null || true
fi
cargo -V

echo "==> Node"
node_ok() {
  command -v node >/dev/null && node -e 'const [a,b]=process.versions.node.split(".").map(Number); process.exit(a>20||(a===20&&b>=19)?0:1)'
}
if ! node_ok; then
  export NVM_DIR="$HOME/.nvm"
  [[ -s "$NVM_DIR/nvm.sh" ]] || curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | bash
  # shellcheck disable=SC1091
  . "$NVM_DIR/nvm.sh"
  nvm install 22
fi
node -v

echo "==> npm packages"
npm ci

echo
echo "Done. Open a new terminal (so PATH picks up cargo/node), then run:"
echo "  scripts/run.sh                      # build + launch"
echo "  scripts/package.sh deb              # or build a .deb to install"
