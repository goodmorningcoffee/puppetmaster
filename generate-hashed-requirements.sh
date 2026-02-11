#!/bin/bash
# Generate hash-pinned requirements.txt for supply chain security
#
# This script generates requirements.txt with cryptographic hashes
# that verify package integrity during installation.
#
# Usage:
#   ./generate-hashed-requirements.sh
#
# After running, commit the updated requirements.txt to version control.

set -e

echo "Installing pip-tools..."
pip install pip-tools -q

echo "Generating hash-pinned requirements.txt..."
pip-compile --generate-hashes requirements.in -o requirements.txt

echo ""
echo "Done! requirements.txt now includes package hashes."
echo ""
echo "To install with hash verification:"
echo "  pip install --require-hashes -r requirements.txt"
echo ""
echo "Remember to commit requirements.txt to version control."
