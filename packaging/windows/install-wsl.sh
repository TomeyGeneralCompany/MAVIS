#!/usr/bin/env bash
# Run as root inside Ubuntu WSL; arguments are Linux paths to the bundled .deb.
set -euo pipefail
deb=${1:?Missing MAVIS Debian package}
[ -f "$deb" ] || { echo "MAVIS installer file missing: $deb" >&2; exit 10; }

# Ollama and the voice engine depend on systemd. Configure without deleting
# other existing WSL configuration and request one controlled WSL restart.
if [ ! -d /run/systemd/system ]; then
    python3 - <<'PY'
from pathlib import Path
import re
p = Path('/etc/wsl.conf')
text = p.read_text() if p.exists() else ''
if re.search(r'(?m)^\s*\[boot\]\s*$', text):
    begin = re.search(r'(?m)^\s*\[boot\]\s*$', text)
    stop = re.search(r'(?m)^\s*\[[^\]]+\]\s*$', text[begin.end():])
    end = begin.end() + stop.start() if stop else len(text)
    body = text[begin.end():end]
    if re.search(r'(?mi)^\s*systemd\s*=', body):
        body = re.sub(r'(?mi)^\s*systemd\s*=.*$', 'systemd=true', body, count=1)
    else:
        body += '\nsystemd=true\n'
    text = text[:begin.end()] + body + text[end:]
else:
    text += '\n[boot]\nsystemd=true\n'
p.write_text(text)
PY
    echo "MAVIS_WSL_RESTART_REQUIRED"
    exit 75
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update
# apt resolves package dependencies and runs MAVIS's one-time provisioning hook.
apt-get install -y --no-install-recommends "$deb"
if ! id mavis >/dev/null 2>&1; then
    useradd --create-home --shell /bin/bash mavis
fi
test -x /usr/bin/mavis
test -x /var/lib/mavis/voice/source/build/qwen-tts
command -v ollama >/dev/null
echo "MAVIS_WSL_INSTALL_COMPLETE"
