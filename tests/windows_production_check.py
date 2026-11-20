"""Exercise an installed Windows build with real local models and test artwork."""
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def main():
    if sys.platform != 'win32':
        raise RuntimeError('This check must run on Windows.')
    import mavis
    install = Path(mavis.__file__).resolve().parent.parent
    from mavis.platform_support import workspace, voice_engine
    root = workspace()
    results = Path(os.environ['MAVIS_TEST_RESULTS'])
    results.mkdir(parents=True, exist_ok=True)
    os.environ.update(TUBE_OFFLINE='1', TUBE_CAPTIONS='1', X264_PRESET='ultrafast', FFMPEG_THREADS='2')
    os.environ['PATH'] = str(install / 'tools') + os.pathsep + os.environ.get('PATH', '')
    os.environ.setdefault('VOICE_ENGINE_DIR', str(root.parent / 'voice'))
    root.mkdir(parents=True, exist_ok=True)
    def save(path, value):
        path.write_text(json.dumps(value, indent=2), encoding='utf-8')
    report = {'platform': sys.platform, 'python': sys.version, 'installed_app': str(install),
              'real_models': True, 'upload_requested': False, 'complete': False}
    report_path = results / 'production-report.json'
    save(report_path, report)

    # Test-only original shapes, no customer/channel artwork or voice recordings.
    from PIL import Image, ImageDraw
    assets = root / 'assets/animation'
    assets.mkdir(parents=True, exist_ok=True)
    def sheet(name, columns, rows):
        image = Image.new('RGBA', (columns * 256, rows * 256))
        draw = ImageDraw.Draw(image)
        for i in range(columns * rows):
            x, y = (i % columns) * 256, (i // columns) * 256
            draw.rounded_rectangle((x+55,y+55,x+200,y+220), radius=24, fill='#01cac4')
            draw.ellipse((x+80,y+80,x+98,y+98), fill='white')
            draw.ellipse((x+155,y+80,x+173,y+98), fill='white')
            draw.line((x+100,y+130,x+155,y+130), fill='#c90823', width=6)
            draw.line((x+80,y+220,x+65+(i%2)*18,y+244), fill='#c90823', width=12)
            draw.line((x+175,y+220,x+190-(i%2)*18,y+244), fill='#c90823', width=12)
        image.save(assets / name)
    sheet('poses.png', 3, 2)
    sheet('walk-cycle.png', 4, 2)
    sheet('puff-cycle.png', 3, 1)
    save(assets / 'walk-cycle.json', [{'mouth': [128, 130], 'floor': 250}] * 8)
    save(assets / 'action-cycle.json', [{'mouth': [128, 130], 'floor': 250}] * 3)
    save(assets / 'approved-animation-sha256.json', {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in assets.iterdir() if p.is_file()})
    save(root / 'media-profile.json', {'brand_name': 'MAVIS Windows Test', 'animation': {'assets_dir': 'assets/animation', 'background_color': '#ffffff'}})
    save(root / 'voice-profile.json', {'provider': 'qwen-local',
        'instruction': 'A clear friendly adult English voice, speaking at a steady conversational pace.',
        'reference_text': 'Welcome to this local video production demonstration. Clear words and a steady pace make the message easy to follow.', 'seed': 42})
    save(root / 'mavis.json', {'mode': 'private', 'topic': 'Simple everyday care for garden hand tools: clean them after use, dry them, and store them neatly. A friendly evergreen explainer with no statistics.'})

    # A throwaway publisher key activates only this disposable installed test copy.
    # The installer artifact retains the real publisher public key throughout.
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
    from mavis.activation import machine_code, payload_bytes
    public_file = install / 'mavis/activation-public.pem'
    original_key = public_file.read_bytes()
    key = Ed25519PrivateKey.generate()
    public_file.write_bytes(key.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo))
    payload = {'version': 1, 'device': machine_code(), 'license_id': 'disposable-windows-ci'}
    save(root / 'activation.json', {'payload': payload, 'signature': base64.b64encode(key.sign(payload_bytes(payload))).decode('ascii')})
    started = time.monotonic()
    try:
        manifest = json.loads((install / 'voice-runtime/model-files.json').read_text())
        for entry in manifest['files']:
            path = voice_engine() / 'models' / entry['rfilename']
            with path.open('rb') as stream:
                digest = hashlib.file_digest(stream, 'sha256').hexdigest()
            if digest != entry['lfs']['sha256']:
                raise RuntimeError('Installed model checksum failed: ' + path.name)
        report['voice_models_verified'] = True
        save(report_path, report)
        subprocess.run([sys.executable, '-X', 'utf8', str(install / 'run_mavis.py'),
                        'run', '--job-id', 'windows-real-production'], check=True, env=os.environ.copy())
        run = root / 'runs/windows-real-production'
        state = json.loads((run / 'checkpoint.json').read_text())
        if not state.get('complete') or not state.get('content', {}).get('script'):
            raise RuntimeError('Production did not complete with a model-written script.')
        from mavis.shorts import validate_short
        info = validate_short(run / 'short.mp4')
        from mavis.upload_metadata import prepare_upload_snippet
        prepare_upload_snippet(state['content'])
        report.update(complete=True, elapsed_seconds=round(time.monotonic()-started, 1),
                      video_duration=info['format']['duration'], stages=state.get('stage_times'),
                      title=state['content']['title'], script_words=len(state['content']['script'].split()))
    except Exception as exc:
        report.update(error=f'{type(exc).__name__}: {exc}', elapsed_seconds=round(time.monotonic()-started, 1))
        raise
    finally:
        public_file.write_bytes(original_key)
        (root / 'activation.json').unlink(missing_ok=True)
        save(report_path, report)
        import shutil
        run = root / 'runs/windows-real-production'
        if run.exists():
            shutil.copytree(run, results / 'production', dirs_exist_ok=True)
        print(json.dumps(report, indent=2), flush=True)

if __name__ == '__main__':
    main()
