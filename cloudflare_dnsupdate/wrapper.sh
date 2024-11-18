#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

HERE="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$HERE"

# Ensure virtual environment directory exists
mkdir -p "$HOME/.venvs"

# Create virtual environment if needed
if [[ ! -d "$HOME/.venvs/cloudflare_dnsupdate" ]]; then
    /usr/bin/python3 -m venv "$HOME/.venvs/cloudflare_dnsupdate"
fi

# Activate the virtual environment
# shellcheck disable=SC1091
source "$HOME/.venvs/cloudflare_dnsupdate/bin/activate"

# Install the requirements
pip3 install -r requirements.txt

# Debug: Ensure the script is executable
chmod 755 dnsupdate.py

# Run the Python script
./dnsupdate.py
