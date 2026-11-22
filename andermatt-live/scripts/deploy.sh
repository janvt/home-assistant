#!/usr/bin/env bash
# Copies the integration to a Home Assistant over SSH (the Terminal & SSH
# add-on), for as long as HACS cannot install it.
#
# The new files replace the old ones only if Home Assistant's config check
# passes; otherwise the old ones are put back.  The check reads the
# configuration, not the integration's code: run the tests first.  Home
# Assistant loads the files on restart, which this asks for, as it takes the
# whole house offline for a bit.
#
#   scripts/deploy.sh               copy, check, ask to restart
#   scripts/deploy.sh --restart     copy, check, restart without asking
#   scripts/deploy.sh --no-restart  copy and check only
#
# Settings come from .deploy.env (copy .deploy.env.example) or the environment.

set -euo pipefail

DOMAIN=andermatt_live
ROOT=$(cd "$(dirname "$0")/.." && pwd)

restart=ask
case "${1:-}" in
  --restart) restart=yes ;;
  --no-restart) restart=no ;;
  "") ;;
  *) echo "usage: $0 [--restart | --no-restart]" >&2; exit 2 ;;
esac

if [[ -f "$ROOT/.deploy.env" ]]; then
  # shellcheck source=/dev/null
  source "$ROOT/.deploy.env"
fi
: "${HA_SSH:?set HA_SSH, e.g. root@homeassistant.local (see .deploy.env.example)}"
HA_SSH_PORT=${HA_SSH_PORT:-22}
HA_SSH_KEY=${HA_SSH_KEY:-$HOME/.ssh/id_ed25519_homeassistant}

ssh_ha() {
  ssh -i "$HA_SSH_KEY" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=10 \
    -p "$HA_SSH_PORT" "$HA_SSH" "$@"
}

cd "$ROOT"
version=$(python3 -c "import json; print(json.load(open('custom_components/$DOMAIN/manifest.json'))['version'])")
commit=$(git rev-parse --short HEAD)
if [[ -n $(git status --porcelain -- "custom_components/$DOMAIN") ]]; then
  echo "Note: custom_components/$DOMAIN has uncommitted changes, which are deployed too."
  commit="$commit+changes"
fi
echo "Deploying $DOMAIN $version ($commit) to $HA_SSH"

# Unpacked next to the old files, then swapped in, so that a failed copy
# leaves the old ones untouched.
COPYFILE_DISABLE=1 tar -C custom_components --exclude=__pycache__ -czf - "$DOMAIN" |
  ssh_ha "set -e
    cd /config/custom_components
    rm -rf .$DOMAIN.new .$DOMAIN.old
    mkdir .$DOMAIN.new
    tar -xzf - -C .$DOMAIN.new
    if [ -e $DOMAIN ]; then mv $DOMAIN .$DOMAIN.old; fi
    mv .$DOMAIN.new/$DOMAIN $DOMAIN
    rmdir .$DOMAIN.new
    if ! ha core check >/dev/null 2>&1; then
      echo 'Config check failed: putting the old files back.' >&2
      rm -rf $DOMAIN
      if [ -e .$DOMAIN.old ]; then mv .$DOMAIN.old $DOMAIN; fi
      ha core check >&2 || true
      exit 1
    fi
    rm -rf .$DOMAIN.old"
echo "Copied, and the config check passes."

if [[ $restart == ask ]]; then
  read -r -p "Restart Home Assistant now to load it? [y/N] " answer
  [[ $answer == [yY]* ]] && restart=yes || restart=no
fi
if [[ $restart == yes ]]; then
  echo "Restarting Home Assistant..."
  ssh_ha "ha core restart"
  echo "Restarted."
else
  echo "Not restarted: Home Assistant loads the new files on its next restart."
fi
