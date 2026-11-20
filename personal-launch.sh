#!/bin/sh
set -eu
source_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
data=${XDG_DATA_HOME:-"$HOME/.local/share"}/mavis
export TUBE_WORKSPACE="${TUBE_WORKSPACE:-$data/workspace}"
export VOICE_ENGINE_DIR="${VOICE_ENGINE_DIR:-/var/lib/mavis/voice}"
python="$data/runtime/bin/python"
if [ ! -x "$python" ]; then
    printf '%s\n' 'Install and set up MAVIS first, or launch local_studio.py using your MAVIS Python environment.' >&2
    exit 1
fi
exec "$python" "$source_dir/local_studio.py" --port 0 "$@"
