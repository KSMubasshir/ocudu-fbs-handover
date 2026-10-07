#!/bin/bash
# Install uv system-wide and resolve the repo's Python helper-script
# dependencies (pyproject.toml / uv.lock) so `uv run bin/<script>.py` works
# for every user immediately after login. Shared by deploy-ocudu.sh and
# setup-cots-ue.sh so all node roles get the same environment. Idempotent.
set -ex
REPODIR=/local/repository

# No uv apt package exists on jammy; install from PyPI into /usr/local.
if ! command -v uv >/dev/null 2>&1; then
  sudo apt-get install -y python3-pip
  sudo -H pip3 install uv
fi

# --frozen: use uv.lock exactly as committed; fail loudly if it is stale.
(cd $REPODIR && uv sync --frozen)
