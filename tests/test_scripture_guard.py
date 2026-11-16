from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ScriptureGuardTests(unittest.TestCase):
    def test_startup_refuses_modified_and_missing_verses(self):
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp)
            package = copy / 'mavis'
            package.mkdir()
            for name in ('__init__.py', 'scripture.py'):
                shutil.copyfile(ROOT / 'mavis' / name, package / name)
            launchers = ('run_mavis.py', 'local_studio.py', 'configure_media.py')
            for name in launchers:
                shutil.copyfile(ROOT / name, copy / name)

            def invoke(*args):
                return subprocess.run([sys.executable, *args], cwd=copy,
                                      capture_output=True, text=True)

            self.assertEqual(invoke('-c', 'import mavis').returncode, 0)
            verse_file = package / 'scripture.py'
            verse_file.write_text(verse_file.read_text().replace('John 1:5', 'John 1:6'))
            for state in ('changed', 'missing'):
                for launcher in launchers:
                    with self.subTest(state=state, launcher=launcher):
                        result = invoke(launcher, '--help')
                        self.assertNotEqual(result.returncode, 0)
                        self.assertEqual(result.stdout, '')
                        self.assertIn(state, result.stderr)
                verse_file.unlink(missing_ok=True)
