#!/usr/bin/env bash
# Sets up the home GitHub Actions runner (label "home") that the Andermatt
# Live checks run on: from home, the Live Dashboard serves its real pages,
# where GitHub's own runners get a bot check now and then.
#
# Run it as root inside a fresh Debian LXC (see "Home runner" in the README),
# with a registration token from the repository's Settings > Actions >
# Runners > New self-hosted runner.  It is valid for an hour and used once:
#
#   read -rs RUNNER_TOKEN && export RUNNER_TOKEN   # paste it, not echoed
#   bash setup-runner.sh
#
# Run it again to update the runner's packages; the registration is kept.
# The runner updates itself.

set -euo pipefail

REPO_URL=https://github.com/janvt/home-assistant
LABELS=home
RUNNER_USER=runner
RUNNER_DIR=/opt/actions-runner
NAME=${RUNNER_NAME:-$(hostname)}

die() { echo "$*" >&2; exit 1; }

[[ $EUID -eq 0 ]] || die "Run as root, inside the runner's container."

# git for actions/checkout, gh for the failure report, jq and curl here.
apt-get update -q
DEBIAN_FRONTEND=noninteractive apt-get install -yq --no-install-recommends \
  ca-certificates curl git gh jq tar

id -u "$RUNNER_USER" >/dev/null 2>&1 ||
  useradd --system --create-home --shell /bin/bash "$RUNNER_USER"

if [[ -f $RUNNER_DIR/.runner ]]; then
  echo "Already registered as $(jq -r .agentName "$RUNNER_DIR/.runner"); packages updated."
  exit 0
fi
: "${RUNNER_TOKEN:?set RUNNER_TOKEN to a registration token (see the top of this script)}"

case $(uname -m) in
  x86_64) arch=x64 ;;
  aarch64) arch=arm64 ;;
  *) die "No runner for $(uname -m)" ;;
esac

# The latest release, checked against the SHA-256 GitHub lists for it.
release=$(curl -fsSL https://api.github.com/repos/actions/runner/releases/latest)
version=$(jq -r .tag_name <<<"$release")
asset="actions-runner-linux-$arch-${version#v}.tar.gz"
url=$(jq -r --arg a "$asset" '.assets[] | select(.name == $a) | .browser_download_url' <<<"$release")
digest=$(jq -r --arg a "$asset" '.assets[] | select(.name == $a) | .digest' <<<"$release")
[[ $digest == sha256:* ]] || die "No checksum for $asset"

echo "Installing the runner $version ($arch) in $RUNNER_DIR"
archive=$(mktemp)
trap 'rm -f "$archive"' EXIT
curl -fsSL -o "$archive" "$url"
echo "${digest#sha256:}  $archive" | sha256sum -c --quiet -
mkdir -p "$RUNNER_DIR"
tar -xzf "$archive" -C "$RUNNER_DIR"
chown -R "$RUNNER_USER": "$RUNNER_DIR"
# The runner's own libraries (ICU and the like).
"$RUNNER_DIR/bin/installdependencies.sh"

cd "$RUNNER_DIR"
runuser -u "$RUNNER_USER" -- ./config.sh --unattended --replace \
  --url "$REPO_URL" --token "$RUNNER_TOKEN" --name "$NAME" --labels "$LABELS"
# A systemd service as the runner user, started now and on every boot.
./svc.sh install "$RUNNER_USER"
./svc.sh start
echo "Registered as $NAME (labels: self-hosted, Linux, $LABELS)."
