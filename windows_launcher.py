"""Entry point for the installed Windows application and scheduler."""
import os
from pathlib import Path
import sys

def main():
    install = Path(__file__).resolve().parent
    if '--workspace' in sys.argv:
        os.environ['TUBE_WORKSPACE'] = sys.argv[sys.argv.index('--workspace') + 1]
    from mavis.platform_support import workspace
    root = workspace()
    root.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault('TUBE_WORKSPACE', str(root))
    os.environ.setdefault('VOICE_ENGINE_DIR', str(root.parent / 'voice'))
    engine = Path(os.environ['VOICE_ENGINE_DIR']) / 'source/build/Release'
    if not (engine / 'qwen-tts.exe').is_file():
        import shutil
        engine.mkdir(parents=True, exist_ok=True)
        for binary in (install / 'voice/source/build/Release').glob('*'):
            shutil.copy2(binary, engine / binary.name)
    os.environ['PATH'] = str(install / 'tools') + os.pathsep + os.environ.get('PATH', '')
    os.environ['PYTHONUTF8'] = '1'
    from dotenv import load_dotenv
    load_dotenv(root / '.env')
    if '--tick' in sys.argv:
        import run_mavis
        sys.argv = [sys.argv[0], 'tick']
        run_mavis.main()
    elif '--setup' in sys.argv:
        import runpy
        runpy.run_path(str(install / 'packaging/windows/provision.py'), run_name='__main__')
    else:
        import local_studio
        sys.argv = [sys.argv[0], '--port', '0']
        local_studio.main()

if __name__ == '__main__':
    try:
        main()
    except Exception:
        import traceback
        from mavis.platform_support import workspace
        root = workspace()
        root.mkdir(parents=True, exist_ok=True)
        with (root / 'windows-error.log').open('a', encoding='utf-8') as log:
            traceback.print_exc(file=log)
        if '--tick' not in sys.argv and '--setup' not in sys.argv:
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, 'MAVIS could not start. See ' + str(root / 'windows-error.log'), 'MAVIS', 16)
        raise
