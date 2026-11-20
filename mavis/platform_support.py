"""Native paths, process locks and scheduling for supported desktops."""
import os
from pathlib import Path
import subprocess
import sys

WINDOWS = sys.platform == 'win32'

def workspace():
    default = Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'MAVIS' / 'data' if WINDOWS else Path.home() / '.tomey-media'
    return Path(os.environ.get('TUBE_WORKSPACE', default)).expanduser().resolve()

def voice_engine():
    default = workspace().parent / 'voice' if WINDOWS else Path.home() / '.local/share/tomey-media-voice'
    return Path(os.environ.get('VOICE_ENGINE_DIR', default)).expanduser()

def voice_binary():
    engine = voice_engine()
    if WINDOWS:
        return engine / 'source/build/Release/qwen-tts.exe'
    return engine / 'source/build/qwen-tts'

def lock_file(stream):
    if WINDOWS:
        import msvcrt
        stream.seek(0)
        try:
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as exc:
            raise BlockingIOError('Another MAVIS job is running') from exc
    else:
        import fcntl
        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)

def runner_busy(root):
    try:
        with (root / 'mavis.lock').open('a+b') as stream:
            lock_file(stream)
    except BlockingIOError:
        return True
    return False

def enable_windows_schedule(root):
    # Run only in this user's interactive session, where OAuth and local models live.
    action = subprocess.list2cmdline([sys.executable, '-X', 'utf8', str(Path(__file__).resolve().parents[1] / 'windows_launcher.py'), '--tick'])
    subprocess.run(['schtasks.exe', '/Create', '/TN', 'MAVIS Production', '/TR', action,
                    '/SC', 'MINUTE', '/MO', '5', '/IT', '/F'], check=True)
