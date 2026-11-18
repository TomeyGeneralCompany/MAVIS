"""Provision third-party MAVIS runtimes during Debian package installation.

Runs as root from dpkg postinst. Downloads are HTTPS, model hashes are verified,
and repeat installations reuse completed components.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
from urllib.request import urlopen

ROOT = Path("/var/lib/mavis")
VOICE = ROOT / "voice"
MODELS = VOICE / "models"
MANIFEST = Path("/usr/share/mavis/voice-runtime/model-files.json")
REPO = "https://github.com/ServeurpersoCom/qwentts.cpp.git"
MODEL_REPO = "Serveurperso/Qwen3-TTS-GGUF"


def command(*args, **kwargs):
    print("[MAVIS setup]", " ".join(map(str, args)), flush=True)
    subprocess.run(list(map(str, args)), check=True, **kwargs)


def download(url, destination, digest=None):
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and (digest is None or sha256(destination) == digest):
        return
    partial = destination.with_name(destination.name + ".partial")
    partial.unlink(missing_ok=True)
    print("[MAVIS setup] Downloading", destination.name, flush=True)
    try:
        with urlopen(url, timeout=60) as source, partial.open("wb") as sink:
            shutil.copyfileobj(source, sink, length=1024 * 1024)
        if digest and sha256(partial) != digest:
            raise RuntimeError("Checksum mismatch for " + destination.name)
        partial.replace(destination)
    finally:
        partial.unlink(missing_ok=True)


def sha256(path):
    hash = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            hash.update(block)
    return hash.hexdigest()


def ollama():
    if not shutil.which("ollama"):
        # Official Ollama Linux installer. Fetch separately so download failures
        # cannot result in executing an incomplete installer.
        with tempfile.TemporaryDirectory() as temp:
            installer = Path(temp) / "ollama-install.sh"
            download("https://ollama.com/install.sh", installer)
            command("sh", installer)
    if shutil.which("systemctl") and Path("/run/systemd/system").exists():
        command("systemctl", "enable", "--now", "ollama.service")
    else:
        raise RuntimeError("Ollama requires a running systemd service on supported Debian desktops.")
    for attempt in range(30):
        try:
            with urlopen("http://127.0.0.1:11434/api/tags", timeout=3):
                break
        except OSError:
            if attempt == 29:
                raise RuntimeError("Ollama service did not become ready.")
            time.sleep(2)
    command("ollama", "pull", "qwen3:4b")


def voice():
    manifest = json.loads(MANIFEST.read_text())
    revision = manifest["revision"]
    for entry in manifest["files"]:
        name = entry["rfilename"]
        download(
            f"https://huggingface.co/{MODEL_REPO}/resolve/{revision}/{name}",
            MODELS / name, entry["lfs"]["sha256"]
        )
    source = VOICE / "source"
    binary = source / "build" / "qwen-tts"
    if not binary.is_file():
        if not (source / ".git").is_dir():
            source.parent.mkdir(parents=True, exist_ok=True)
            command("git", "clone", "--depth", "1", REPO, source)
        command("cmake", "-S", source, "-B", source / "build", "-DCMAKE_BUILD_TYPE=Release")
        command("cmake", "--build", source / "build", "--target", "qwen-tts", "-j", "2")
    if not binary.is_file():
        raise RuntimeError("Qwen voice engine build finished without the qwen-tts executable.")


if __name__ == "__main__":
    ROOT.mkdir(mode=0o755, parents=True, exist_ok=True)
    ollama()
    voice()
    print("[MAVIS setup] All local production runtimes are ready.", flush=True)
