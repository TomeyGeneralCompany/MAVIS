"""Platform behavior shared by Linux checks and native Windows CI."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock
from mavis import platform_support as platform
from mavis.activation import machine_code, ActivationRequired

class WindowsPlatformTests(unittest.TestCase):
    def test_windows_default_paths_and_override(self):
        with patch.object(platform, 'WINDOWS', True), patch.dict(os.environ, {'LOCALAPPDATA': str(Path.home() / 'AppData/Local')}):
            self.assertEqual(platform.workspace(), (Path.home() / 'AppData/Local/MAVIS/data').resolve())
            self.assertEqual(platform.voice_binary().name, 'qwen-tts.exe')
            with patch.dict(os.environ, {'TUBE_WORKSPACE': str(Path.home() / 'custom')}):
                self.assertEqual(platform.workspace(), (Path.home() / 'custom').resolve())

    def test_lock_is_exclusive_across_processes_and_releases(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with (root / 'mavis.lock').open('a+b') as stream:
                platform.lock_file(stream)
                command = [sys.executable, '-c', 'from pathlib import Path; from mavis.platform_support import runner_busy; import sys; sys.exit(0 if runner_busy(Path(sys.argv[1])) else 1)', str(root)]
                self.assertEqual(subprocess.run(command, check=False).returncode, 0)
            self.assertFalse(platform.runner_busy(root))

    def test_windows_machine_guid_and_missing_identifier(self):
        registry = MagicMock()
        registry.QueryValueEx.return_value = ('12345678-1234-1234-1234-123456789abc', 1)
        with patch('mavis.activation.os.name', 'nt'), patch.dict(sys.modules, {'winreg': registry}):
            self.assertEqual(len(machine_code()), 64)
            registry.QueryValueEx.return_value = ('invalid', 1)
            with self.assertRaises(ActivationRequired):
                machine_code()

    def test_task_scheduler_preserves_paths_with_spaces(self):
        with patch.object(platform.subprocess, 'run') as run:
            platform.enable_windows_schedule(Path.home())
        args = run.call_args.args[0]
        self.assertEqual(args[0], 'schtasks.exe')
        self.assertIn('/IT', args)
        self.assertIn('windows_launcher.py', args[args.index('/TR') + 1])
        self.assertIn('utf8', args[args.index('/TR') + 1])
