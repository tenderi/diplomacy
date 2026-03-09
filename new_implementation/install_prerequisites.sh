#!/usr/bin/env bash
# Install prerequisites for running the Diplomacy server and browser frontend locally.
# Supports: Arch Linux, Debian/Ubuntu, macOS (Homebrew).
# Usage: ./install_prerequisites.sh   (or: bash install_prerequisites.sh)

set -e

echo "=== Diplomacy: install prerequisites ==="

detect_os() {
    if [[ -f /etc/arch-release ]]; then
        echo "arch"
    elif [[ -f /etc/debian_version ]]; then
        echo "debian"
    elif [[ "$(uname -s)" == "Darwin" ]]; then
        echo "macos"
    else
        echo "unknown"
    fi
}

install_arch() {
    echo "[Arch] Refreshing package databases (to get latest versions)..."
    sudo pacman -Sy
    echo "[Arch] Installing/upgrading packages..."
    sudo pacman -S --needed --noconfirm python python-pip postgresql nodejs npm
    echo "[Arch] Starting PostgreSQL..."
    sudo systemctl start postgresql || true
    sudo systemctl enable postgresql 2>/dev/null || true
}

install_debian() {
    echo "[Debian/Ubuntu] Updating package list (to get latest versions)..."
    sudo apt-get update -qq
    echo "[Debian/Ubuntu] Installing/upgrading packages to latest from repos..."
    sudo apt-get install -y python3 python3-pip python3-venv postgresql postgresql-client
    # Node.js: use Node 24 from NodeSource if missing or outdated
    if ! command -v node &>/dev/null || [[ $(node -v | cut -d. -f1 | tr -d v) -lt 22 ]]; then
        echo "[Debian/Ubuntu] Adding NodeSource repo and installing Node.js 24..."
        curl -fsSL https://deb.nodesource.com/setup_24.x | sudo -E bash -
        sudo apt-get update -qq
        sudo apt-get install -y nodejs
    else
        echo "[Debian/Ubuntu] Node.js already present: $(node -v)"
    fi
    echo "[Debian/Ubuntu] Starting PostgreSQL..."
    sudo systemctl start postgresql || true
}

install_macos() {
    if ! command -v brew &>/dev/null; then
        echo "Homebrew is required on macOS. Install from https://brew.sh"
        exit 1
    fi
    echo "[macOS] Updating Homebrew (to get latest formulae)..."
    brew update
    echo "[macOS] Installing/upgrading packages..."
    brew install python postgresql@16 node
    brew upgrade python postgresql@16 node 2>/dev/null || true
    echo "[macOS] Starting PostgreSQL..."
    brew services start postgresql@16 2>/dev/null || true
}

OS=$(detect_os)
echo "Detected OS: $OS"

case "$OS" in
    arch)   install_arch ;;
    debian) install_debian ;;
    macos)  install_macos ;;
    *)
        echo "Unsupported OS. Install manually: Python 3.8+, PostgreSQL, Node.js 18+ and npm."
        exit 1
        ;;
esac

echo ""
echo "=== Verifying installations ==="
python3 --version  || echo "WARNING: python3 not in PATH"
command -v pip3 &>/dev/null && pip3 --version || pip --version || echo "WARNING: pip not found"
psql --version     || echo "WARNING: psql not in PATH (PostgreSQL client)"
node --version     || echo "WARNING: node not in PATH"
npm --version      || echo "WARNING: npm not in PATH"
echo ""
echo "Done. Next steps:"
echo "  1. Create DB user and database (see docs/LOCAL_DEVELOPMENT.md §3.2)"
echo "  2. cd new_implementation && python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
echo "  3. alembic upgrade head"
echo "  4. PYTHONPATH=src uvicorn server._api_module:app --host 0.0.0.0 --port 8000"
echo "  5. (optional) cd frontend && npm install && npm run dev  → http://localhost:5173"
