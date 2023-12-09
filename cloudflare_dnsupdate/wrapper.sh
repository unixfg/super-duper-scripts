#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'
export PS4='+(${BASH_SOURCE}:${LINENO}): S{FUNCNAME[0]:+${FUNCNAME [0]}(): }'
# shellcheck disable=SC2034
HERE="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$HERE"

# Ensure virtual environment directory exists
mkdir -p "$HOME/.venvs"

# Create virtual environment if needed
if [[ ! -d "$HOME/.venvs/cloudflare_dnsupdate" ]]; then
    python3 -m venv "$HOME/.venvs/cloudflare_dnsupdate"
fi

# Activate the virtual environment
# shellcheck disable=SC1091
source "$HOME/.venvs/cloudflare_dnsupdate/bin/activate"

# Install the requirements
pip3 install -r requirements.txt

chmod 755 run.sh
chmod 755 dnsupdate.py
./dnsupdate.py