"""Download verified voice models and prepare the Windows local writer."""
import importlib.util
from pathlib import Path
import shutil
import subprocess
import time
import tempfile
from urllib.request import urlopen


def main():
    install = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location('provision_common', install / 'packaging/provision.py')
    common = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(common)
    from mavis.platform_support import voice_engine, voice_binary
    engine = voice_engine()
    if not voice_binary().is_file():
        raise RuntimeError('The installed Windows voice engine is missing. Reinstall MAVIS.')
    import json
    manifest = json.loads((install / 'voice-runtime/model-files.json').read_text())
    for entry in manifest['files']:
        name = entry['rfilename']
        common.download(f"https://huggingface.co/{common.MODEL_REPO}/resolve/{manifest['revision']}/{name}",
                        engine / 'models' / name, entry['lfs']['sha256'])
    ollama = shutil.which('ollama') or str(Path.home() / 'AppData/Local/Programs/Ollama/ollama.exe')
    if not Path(ollama).is_file():
        with tempfile.TemporaryDirectory() as folder:
            installer = Path(folder) / 'OllamaSetup.exe'
            common.download('https://ollama.com/download/OllamaSetup.exe', installer)
            # Use an environment variable, never interpolate paths into PowerShell code.
            import os
            verify = ("$ErrorActionPreference = 'Stop'; "
                      "Import-Module (Join-Path $PSHOME 'Modules/Microsoft.PowerShell.Security'); "
                      "$s = Get-AuthenticodeSignature -LiteralPath $env:MAVIS_INSTALLER; "
                      "if ($s.Status -ne 'Valid') { throw 'Installer signature is invalid' }")
            verify_env = {k: v for k, v in os.environ.items() if k.lower() != 'psmodulepath'}
            verify_env['MAVIS_INSTALLER'] = str(installer)
            powershell = Path(os.environ['SystemRoot']) / 'System32/WindowsPowerShell/v1.0/powershell.exe'
            subprocess.run([str(powershell), '-NoProfile', '-NonInteractive', '-Command', verify],
                           env=verify_env, check=True)
            subprocess.run([str(installer), '/VERYSILENT', '/NORESTART', '/SUPPRESSMSGBOXES'], check=True)
        if not Path(ollama).is_file():
            raise RuntimeError('Ollama installation failed. Run MAVIS Setup again.')
    for attempt in range(30):
        try:
            with urlopen('http://127.0.0.1:11434/api/tags', timeout=2):
                break
        except OSError:
            if attempt == 0:
                subprocess.Popen([ollama, 'serve'], creationflags=subprocess.CREATE_NO_WINDOW)
            if attempt == 29:
                raise RuntimeError('Ollama did not start. Open Ollama and run MAVIS Setup again.')
            time.sleep(2)
    subprocess.run([ollama, 'pull', 'qwen3:4b'], check=True)
    print('MAVIS Windows local runtimes are ready.', flush=True)

if __name__ == '__main__':
    main()
