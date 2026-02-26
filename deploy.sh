#!/usr/bin/env bash
# Bookaboo deployment script
# Usage (one-liner):
#   curl -fsSL https://raw.githubusercontent.com/DevinPillemer/bookaboo/main/deploy.sh | bash
# Or with a specific token for a private repo:
#   curl -fsSL https://raw.githubusercontent.com/DevinPillemer/bookaboo/main/deploy.sh | bash -s -- --token ghp_YOURTOKEN
set -euo pipefail

# ── Config ────────────────────────────────────────────────────────────────────
REPO_URL="https://github.com/DevinPillemer/bookaboo.git"
INSTALL_DIR="/opt/bookaboo"
SERVICE_NAME="bookaboo"
SERVICE_USER="bookaboo"
PORT=8000
PYTHON_MIN="3.10"

# ── Colour helpers ────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'
info()    { echo -e "${CYAN}${BOLD}[bookaboo]${RESET} $*"; }
success() { echo -e "${GREEN}${BOLD}[bookaboo]${RESET} $*"; }
warn()    { echo -e "${YELLOW}${BOLD}[bookaboo]${RESET} $*"; }
die()     { echo -e "${RED}${BOLD}[bookaboo] ERROR:${RESET} $*" >&2; exit 1; }

# ── Argument parsing ──────────────────────────────────────────────────────────
TOKEN=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --token) TOKEN="$2"; shift 2 ;;
    *) warn "Unknown arg: $1"; shift ;;
  esac
done

if [[ -n "$TOKEN" ]]; then
  REPO_URL="https://${TOKEN}@github.com/DevinPillemer/bookaboo.git"
fi

# ── Root check ────────────────────────────────────────────────────────────────
[[ "$EUID" -eq 0 ]] || die "Run as root (sudo bash deploy.sh)"

# ── OS detection & package install ───────────────────────────────────────────
info "Detecting OS..."
if command -v apt-get &>/dev/null; then
  PKG_MGR="apt-get"
  apt-get update -qq
  apt-get install -y -qq git python3 python3-pip python3-venv curl
elif command -v dnf &>/dev/null; then
  PKG_MGR="dnf"
  dnf install -y -q git python3 python3-pip curl
elif command -v yum &>/dev/null; then
  PKG_MGR="yum"
  yum install -y -q git python3 python3-pip curl
else
  die "Unsupported package manager. Install git and python3 manually."
fi
success "System packages ready (via $PKG_MGR)"

# ── Python version check ──────────────────────────────────────────────────────
PYTHON=$(command -v python3 || command -v python)
PY_VER=$("$PYTHON" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
info "Python version: $PY_VER"
python3 -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" \
  || die "Python $PYTHON_MIN+ required (found $PY_VER)"

# ── Service user ──────────────────────────────────────────────────────────────
if ! id "$SERVICE_USER" &>/dev/null; then
  info "Creating system user '$SERVICE_USER'..."
  useradd --system --no-create-home --shell /usr/sbin/nologin "$SERVICE_USER"
  success "User '$SERVICE_USER' created"
else
  info "User '$SERVICE_USER' already exists"
fi

# ── Clone or update repo ──────────────────────────────────────────────────────
if [[ -d "$INSTALL_DIR/.git" ]]; then
  info "Updating existing repo at $INSTALL_DIR..."
  # Mask the token in output
  git -C "$INSTALL_DIR" remote set-url origin "$REPO_URL" 2>/dev/null || true
  git -C "$INSTALL_DIR" fetch --quiet origin
  git -C "$INSTALL_DIR" reset --hard origin/main
  success "Repo updated"
else
  info "Cloning repo to $INSTALL_DIR..."
  git clone --quiet "$REPO_URL" "$INSTALL_DIR"
  success "Repo cloned"
fi

# Strip token from stored remote URL to avoid leaking it
if [[ -n "$TOKEN" ]]; then
  git -C "$INSTALL_DIR" remote set-url origin \
    "https://github.com/DevinPillemer/bookaboo.git"
fi

# ── Virtual environment & dependencies ───────────────────────────────────────
VENV="$INSTALL_DIR/.venv"
if [[ ! -d "$VENV" ]]; then
  info "Creating virtual environment..."
  "$PYTHON" -m venv "$VENV"
fi
info "Installing Python dependencies..."
"$VENV/bin/pip" install --quiet --upgrade pip
"$VENV/bin/pip" install --quiet -r "$INSTALL_DIR/requirements.txt"
success "Dependencies installed"

# ── .env file ────────────────────────────────────────────────────────────────
ENV_FILE="$INSTALL_DIR/.env"
if [[ ! -f "$ENV_FILE" ]]; then
  info "Creating .env from template..."
  cp "$INSTALL_DIR/.env.example" "$ENV_FILE"
  sed -i "s/^BOOKABOO_PORT=.*/BOOKABOO_PORT=$PORT/" "$ENV_FILE"
  chmod 600 "$ENV_FILE"
  success ".env created at $ENV_FILE (edit to add API key)"
else
  info ".env already exists — skipping"
fi

# ── File ownership ────────────────────────────────────────────────────────────
chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR"
# Config dir for runtime data
CONFIG_DIR="/home/$SERVICE_USER/.config/restaurant-reservations"
mkdir -p "$CONFIG_DIR"
chown -R "$SERVICE_USER:$SERVICE_USER" "/home/$SERVICE_USER" 2>/dev/null || true
# Use /var/lib as fallback home for system users with no home dir
CONFIG_DIR="/var/lib/bookaboo"
mkdir -p "$CONFIG_DIR"
chown -R "$SERVICE_USER:$SERVICE_USER" "$CONFIG_DIR"

# ── systemd service ───────────────────────────────────────────────────────────
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
info "Writing systemd unit to $SERVICE_FILE..."
cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=Bookaboo Restaurant Reservation API
After=network.target
Wants=network-online.target

[Service]
Type=exec
User=${SERVICE_USER}
Group=${SERVICE_USER}
WorkingDirectory=${INSTALL_DIR}
EnvironmentFile=-${ENV_FILE}
Environment="HOME=/var/lib/bookaboo"
ExecStart=${VENV}/bin/uvicorn api_server:app --host 0.0.0.0 --port ${PORT} --no-access-log
ExecReload=/bin/kill -HUP \$MAINPID
Restart=on-failure
RestartSec=5s
# Security hardening
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ReadWritePaths=${INSTALL_DIR} /var/lib/bookaboo
ProtectHome=read-only

[Install]
WantedBy=multi-user.target
EOF
success "systemd unit written"

# ── Enable & (re)start service ───────────────────────────────────────────────
systemctl daemon-reload
systemctl enable "$SERVICE_NAME"

if systemctl is-active --quiet "$SERVICE_NAME"; then
  info "Restarting $SERVICE_NAME..."
  systemctl restart "$SERVICE_NAME"
else
  info "Starting $SERVICE_NAME..."
  systemctl start "$SERVICE_NAME"
fi

sleep 2  # brief pause so the service has time to bind

if systemctl is-active --quiet "$SERVICE_NAME"; then
  success "${BOLD}Bookaboo is running!${RESET}"
  echo ""
  echo -e "  ${BOLD}Service:${RESET}  systemctl status $SERVICE_NAME"
  echo -e "  ${BOLD}Logs:${RESET}     journalctl -u $SERVICE_NAME -f"
  echo -e "  ${BOLD}API:${RESET}      http://$(hostname -I | awk '{print $1}'):${PORT}"
  echo -e "  ${BOLD}Health:${RESET}   http://$(hostname -I | awk '{print $1}'):${PORT}/health"
  echo -e "  ${BOLD}Docs:${RESET}     http://$(hostname -I | awk '{print $1}'):${PORT}/docs"
  echo ""
else
  die "Service failed to start. Check: journalctl -u $SERVICE_NAME -n 50 --no-pager"
fi
