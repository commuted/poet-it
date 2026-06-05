#!/bin/sh
# Generates python3-requirements.json for offline Flatpak builds (required for Flathub).
# Run this once, and again whenever dependencies in requirements.txt change.
#
# Requires flatpak-pip-generator:
#   pip install flatpak-pip-generator
set -e
cd "$(dirname "$0")"
flatpak-pip-generator -r requirements.txt -o python3-requirements.json
echo "python3-requirements.json written."
