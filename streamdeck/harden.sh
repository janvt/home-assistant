#!/usr/bin/env bash
#
# Idempotently apply the HOST-LEVEL hardening/resilience steps from the README
# ("Resilience → Host-level steps", plus the required USB udev rule and
# docker-on-boot). Safe to re-run — each step checks before changing.
#
# Needs sudo (prompts as required). Does NOT reboot; it tells you when a reboot
# is required. Container-level hardening (unprivileged, cap_drop, healthcheck,
# autoheal, log rotation, pinned digest) lives in docker-compose.yaml and is
# applied by `task up` / `task deploy`, not here. Hardware/manual steps
# (USB-SSD boot, PSU) are reported, not automated.
#
# Run via: task harden
set -euo pipefail

CHANGED=0
REBOOT=0
ok()  { printf '  [ok]  %s\n' "$*"; }
set_() { printf '  [SET] %s\n' "$*"; CHANGED=1; }
note() { printf '        %s\n' "$*"; }

echo "Hardening host (idempotent)…"

# 1. udev rule — required so the *unprivileged* container can reach the deck.
RULE=/etc/udev/rules.d/70-streamdeck.rules
RULE_CONTENT='SUBSYSTEMS=="usb", ATTRS{idVendor}=="0fd9", GROUP="users", TAG+="uaccess"'
if [ "$(sudo cat "$RULE" 2>/dev/null || true)" != "$RULE_CONTENT" ]; then
  echo "$RULE_CONTENT" | sudo tee "$RULE" >/dev/null
  sudo udevadm control --reload-rules
  sudo udevadm trigger
  set_ "wrote $RULE + reloaded udev (reconnect the deck if not detected)"
else
  ok "udev rule present"
fi

# 2. Docker starts on boot (so restart: unless-stopped actually survives reboots)
if systemctl is-enabled --quiet docker 2>/dev/null; then
  ok "docker enabled on boot"
else
  sudo systemctl enable docker
  set_ "enabled docker on boot"
fi

# 3. Hardware watchdog — recovers from a total kernel freeze. Needs a reboot.
CFG=/boot/firmware/config.txt
[ -f "$CFG" ] || CFG=/boot/config.txt
if grep -qxF 'dtparam=watchdog=on' "$CFG" 2>/dev/null; then
  ok "watchdog dtparam present ($CFG)"
else
  echo 'dtparam=watchdog=on' | sudo tee -a "$CFG" >/dev/null
  set_ "enabled watchdog device in $CFG"; REBOOT=1
fi
SYSCONF=/etc/systemd/system.conf
if grep -qxF 'RuntimeWatchdogSec=15' "$SYSCONF"; then
  ok "RuntimeWatchdogSec=15 set"
else
  sudo sed -i 's/^#\?RuntimeWatchdogSec=.*/RuntimeWatchdogSec=15/' "$SYSCONF"
  grep -qxF 'RuntimeWatchdogSec=15' "$SYSCONF" \
    || echo 'RuntimeWatchdogSec=15' | sudo tee -a "$SYSCONF" >/dev/null
  set_ "set RuntimeWatchdogSec=15 in $SYSCONF"; REBOOT=1
fi

# 4. Unattended security upgrades
if dpkg -s unattended-upgrades >/dev/null 2>&1; then
  ok "unattended-upgrades installed"
else
  sudo apt-get update -qq
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y unattended-upgrades >/dev/null
  set_ "installed unattended-upgrades"
fi
AUTO=/etc/apt/apt.conf.d/20auto-upgrades
AUTO_CONTENT='APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";'
if [ "$(sudo cat "$AUTO" 2>/dev/null || true)" = "$AUTO_CONTENT" ]; then
  ok "unattended-upgrades enabled"
else
  printf '%s\n' "$AUTO_CONTENT" | sudo tee "$AUTO" >/dev/null
  set_ "enabled unattended-upgrades ($AUTO)"
fi

# 5. Time sync — TLS + the long-lived token are time-sensitive.
if [ "$(timedatectl show -p NTP --value 2>/dev/null)" = "yes" ]; then
  ok "NTP time sync enabled"
else
  sudo timedatectl set-ntp true
  set_ "enabled NTP time sync"
fi
if [ "$(timedatectl show -p NTPSynchronized --value 2>/dev/null)" = "yes" ]; then
  ok "clock synchronized"
else
  note "clock not synchronized yet — give it a minute"
fi

# 6. log2ram — RAM-back /var/log to cut SD-card writes (we're staying on SD).
# Installs from the third-party azlux apt repo (the upstream/standard source for
# log2ram). Needs a reboot to take effect. Default config RAM-backs /var/log at
# 40M, which covers journald/syslog churn; container logs live under
# /var/lib/docker (already size-capped in compose), not /var/log.
if dpkg -s log2ram >/dev/null 2>&1; then
  ok "log2ram installed"
else
  KEYRING=/usr/share/keyrings/azlux-archive-keyring.gpg
  LIST=/etc/apt/sources.list.d/azlux.list
  [ -s "$KEYRING" ] || sudo curl -fsSL https://azlux.fr/repo.gpg -o "$KEYRING"
  echo "deb [signed-by=$KEYRING] http://packages.azlux.fr/debian/ stable main" \
    | sudo tee "$LIST" >/dev/null
  sudo apt-get update -qq
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y log2ram >/dev/null
  set_ "installed log2ram (RAM-backed /var/log; azlux repo)"; REBOOT=1
fi

# Manual / hardware steps this script can't (or shouldn't) do.
echo
echo "Manual steps (not automated — see README 'Resilience'):"
note "- Boot from a USB SSD instead of the SD card (Pi 5 supports it)."
note "- Use the official 27W USB-C PD PSU to avoid brownout reset loops."
note "- Bump the pinned image digest deliberately (README 'Pinning the image')."
note "- Container-level hardening is applied by 'task up' / 'task deploy'."

echo
if [ "$REBOOT" = 1 ]; then
  echo ">> Reboot required for the watchdog to take effect:  sudo reboot"
elif [ "$CHANGED" = 1 ]; then
  echo ">> Done — changes applied."
else
  echo ">> Already hardened — nothing to change."
fi
