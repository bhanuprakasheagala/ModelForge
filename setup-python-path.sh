#!/usr/bin/env bash
set -euo pipefail

if [[ $(uname -m) == "arm64" ]]; then
    python_bin_dir="/opt/homebrew/opt/python@3.12/bin"
else
    python_bin_dir="/usr/local/opt/python@3.12/bin"
fi

if [[ ! -d "$python_bin_dir" ]]; then
    printf 'Python 3.12 Homebrew directory not found: %s\n' "$python_bin_dir" >&2
    exit 1
fi

zshrc="${HOME}/.zshrc"
export_line="export PATH=\"$python_bin_dir:\$PATH\""
if ! grep -Fqx "$export_line" "$zshrc" 2>/dev/null; then
    printf '%s\n' "$export_line" >> "$zshrc"
fi
