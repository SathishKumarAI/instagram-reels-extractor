#!/usr/bin/env bash
# Install a systemd USER timer that runs `reels-scrap sync --claude-only` on a
# schedule — no sudo, no root. Incremental + dead-letter make it safe to automate.
#
#   bash scripts/setup-scheduled-sync.sh [OnCalendar]
#   e.g.  bash scripts/setup-scheduled-sync.sh "*-*-* 03:00:00"   (nightly 3am, default)
#         bash scripts/setup-scheduled-sync.sh "hourly"
#
# Manage:  systemctl --user {status|start|stop|disable} reels-sync.timer
# Logs:    journalctl --user -u reels-sync.service -f
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
RS="$REPO/.venv/bin/reels-scrap"
CAL="${1:-*-*-* 03:00:00}"
UNIT_DIR="$HOME/.config/systemd/user"
mkdir -p "$UNIT_DIR"

[ -x "$RS" ] || { echo "✗ $RS not found — set up the venv first (see docs/SYNC.md)"; exit 1; }

cat > "$UNIT_DIR/reels-sync.service" <<EOF
[Unit]
Description=reels-scrap incremental sync (claude-only)
After=network-online.target

[Service]
Type=oneshot
WorkingDirectory=$REPO
ExecStart=$RS sync --config config-claude.yaml --claude-only
EOF

cat > "$UNIT_DIR/reels-sync.timer" <<EOF
[Unit]
Description=Run reels-scrap sync on a schedule

[Timer]
OnCalendar=$CAL
Persistent=true

[Install]
WantedBy=timers.target
EOF

systemctl --user daemon-reload
systemctl --user enable --now reels-sync.timer

echo "✓ scheduled: reels-sync.timer @ '$CAL'"
echo "  next run:"; systemctl --user list-timers reels-sync.timer --no-pager | sed -n '2p'
echo "  logs: journalctl --user -u reels-sync.service -f"
echo "  NOTE: needs linger for runs while logged out — 'loginctl enable-linger $USER' (one-time, may prompt)."
