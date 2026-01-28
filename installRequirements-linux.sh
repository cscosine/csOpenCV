#!/bin/bash

# Install required packages for Linux (Debian/Ubuntu)


set -euo pipefail # enable strict mode

if [ -t 0 ]; then
    # if running in interactive terminal, ask for password if needed
    SUDO="sudo"
else
    # if running in a non-interactive terminal (e.g. in CI workflows), use sudo without password prompt (fail if password is needed)
    SUDO="sudo -n"
fi

packages=(
  # add required packages here
)

missing=()

for pkg in "${packages[@]}"; do
  dpkg -s "$pkg" &>/dev/null || missing+=("$pkg")
done

if [ ${#missing[@]} -ne 0 ]; then
  echo "Need to install missing packages: ${missing[*]}"
  sudo apt install -y "${missing[@]}"
else
  echo "All packages already installed."
fi
