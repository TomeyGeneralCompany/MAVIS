"""Build a Debian desktop package. Requires dpkg-deb."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
FILES = ("studio.html", "local_studio.py", "run_mavis.py", "configure_media.py",
         "requirements.txt", "packaging/provision.py", "mavis/activation-public.pem", "mavis/patristic_index.json", ".env.example", "examples/channel-settings.json",
         "examples/media-profile.json", "examples/voice-profile.json",
         "voice-runtime/model-files.json", "voice-runtime/LICENSE-engine.txt")

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('target', type=Path)
args = parser.parse_args()
args.target.parent.mkdir(parents=True, exist_ok=True)
with TemporaryDirectory() as directory:
    root = Path(directory)
    app = root / 'usr/share/mavis'
    for name in (*FILES, *(str(p.relative_to(ROOT)) for p in (ROOT / 'mavis').glob('*.py'))):
        target = app / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
    (app / 'subscription.json').write_text(json.dumps({'required': False, 'url': ''}))
    for source, target, mode in (
        ('debian-launch.sh', 'usr/bin/mavis', 0o755),
        ('icon.png', 'usr/share/icons/hicolor/128x128/apps/mavis.png', 0o644),
        ('mavis.desktop', 'usr/share/applications/mavis.desktop', 0o644),
        ('postinst', 'DEBIAN/postinst', 0o755),
    ):
        dest = root / target
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / 'packaging' / source, dest)
        dest.chmod(mode)
    (root / 'DEBIAN').mkdir(exist_ok=True)
    (root / 'DEBIAN/control').write_text(
        'Package: mavis\nVersion: 0.2.0\nArchitecture: all\n'
        'Maintainer: Tomey General Company LLC\n'
        'Depends: python3, python3-venv, ffmpeg, xdg-utils, util-linux, curl, git, cmake, build-essential, ca-certificates\n'
        'Description: MAVIS local video production studio\n')
    subprocess.run(['dpkg-deb', '--root-owner-group', '--build', directory, str(args.target)], check=True)
