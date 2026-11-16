from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ScriptureGuardTests(unittest.TestCase):
    def test_each_embedded_verse_is_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            package = Path(tmp) / 'mavis'
            shutil.copytree(ROOT / 'mavis', package, ignore=shutil.ignore_patterns('__pycache__'))
            marker = re.compile(r'^\s*# (?:\d )?[A-Za-z]+ \d+:\d+ — ')
            count = 0
            for path in package.glob('*.py'):
                original = path.read_text()
                lines = original.splitlines(keepends=True)
                for index, line in enumerate(lines):
                    if not marker.match(line):
                        continue
                    count += 1
                    with self.subTest(file=path.name, line=index+1):
                        path.write_text(''.join(lines[:index] + lines[index+1:]))
                        result = subprocess.run([sys.executable, '-c', 'import mavis'], cwd=tmp,
                                                capture_output=True, text=True)
                        self.assertNotEqual(result.returncode, 0)
                        self.assertIn('embedded scripture', result.stderr)
                    path.write_text(original)
            self.assertEqual(count, 33)

    def test_startup_refuses_modified_and_missing_verses(self):
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp)
            package = copy / 'mavis'
            package.mkdir()
            for path in (ROOT / 'mavis').glob('*.py'):
                shutil.copyfile(path, package / path.name)
            launchers = ('run_mavis.py', 'local_studio.py', 'configure_media.py')
            for name in launchers:
                shutil.copyfile(ROOT / name, copy / name)

            def invoke(*args):
                return subprocess.run([sys.executable, *args], cwd=copy,
                                      capture_output=True, text=True)

            self.assertEqual(invoke('-c', 'import mavis').returncode, 0)
            for name, reference in (('media_research.py', 'Proverbs 18:17'),
                                    ('local_voice.py', 'Psalm 19:14'),
                                    ('shorts.py', '1 Corinthians 14:40')):
                path = package / name
                original = path.read_text()
                changed = original.replace(reference, 'removed reference')
                deleted = '\n'.join(line for line in original.split('\n') if reference not in line)
                for text in (changed, deleted):
                    path.write_text(text)
                    with self.subTest(module=name):
                        for launcher in launchers:
                            result = invoke(launcher, '--help')
                            self.assertNotEqual(result.returncode, 0)
                            self.assertEqual(result.stdout, '')
                            self.assertIn(f'embedded scripture in {name}', result.stderr)
                path.write_text(original + '\n# Ordinary source edit.\n')
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
