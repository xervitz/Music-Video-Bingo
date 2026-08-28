#!/usr/bin/env bash

set -euo pipefail

project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$project_dir"

has_libpulse() {
    command -v ldconfig >/dev/null 2>&1 \
        && ldconfig -p 2>/dev/null \
        | awk '/libpulse[.]so[.]0/{found=1} END{exit !found}'
}

if ! has_libpulse; then
    echo "Qt Multimedia requires libpulse.so.0, but it is not installed."
    if command -v apt-get >/dev/null 2>&1 && [[ -t 0 ]]; then
        read -r -p "Install Ubuntu package libpulse0 now? [y/N] " answer
        case "$answer" in
            y|Y|yes|YES)
                sudo apt-get update
                sudo apt-get install -y libpulse0
                ;;
            *)
                echo "Install it later with: sudo apt install libpulse0"
                exit 1
                ;;
        esac
    else
        echo "Install your distribution's package providing libpulse.so.0, then run this again."
        echo "Ubuntu: sudo apt install libpulse0"
        exit 1
    fi
fi

python_path="$project_dir/.venv/bin/python"
if [[ ! -x "$python_path" ]]; then
    echo "Creating project virtual environment..."
    python3 -m venv "$project_dir/.venv"
fi

if ! "$python_path" -m pip show PySide6 >/dev/null 2>&1; then
    echo "Installing Python requirements..."
    "$python_path" -m pip install -r "$project_dir/requirements.txt"
fi

exec "$python_path" "$project_dir/main.py"
