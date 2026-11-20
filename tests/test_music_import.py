import argparse
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import fetch_music


class MusicImportTests(unittest.TestCase):
    def test_source_validation_and_bounded_audio_command(self):
        for url in ['http://youtube.com/watch?v=x', 'https://youtube.com.evil.test/x',
                    'file:///tmp/song', 'https://user@youtube.com/x']:
            with self.assertRaises(argparse.ArgumentTypeError):
                fetch_music.youtube_url(url)
        with tempfile.TemporaryDirectory() as tmp, patch.object(fetch_music, 'ffmpeg_path', return_value='/bin/ffmpeg'), \
                patch.object(fetch_music.subprocess, 'run') as run, \
                patch.object(fetch_music, 'catalog', return_value={'sources': 0}):
            run.return_value.returncode = 1
            result = fetch_music.fetch(tmp, ['https://youtu.be/Y9YCykJUQ7E'], 3)
            command = run.call_args.args[0]
            self.assertIn('--no-playlist', command)
            self.assertEqual(command[command.index('--playlist-end') + 1], '3')
            self.assertIn('--download-archive', command)
            self.assertEqual(result['download_exit_code'], 1)

    @unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'FFmpeg required')
    def test_real_audio_catalog_recovery_duplicates_and_incomplete_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sources = root / 'music/sources'
            sources.mkdir(parents=True)
            subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
                            'sine=frequency=440:duration=1', '-c:a', 'aac',
                            str(sources / 'fixture.m4a')], check=True)
            metadata = {'id': 'fixture', 'title': 'Test jazz', 'channel': 'Test channel',
                        'webpage_url': 'https://youtu.be/fixture',
                        'description': 'Source description',
                        'chapters': [{'start_time': 0, 'end_time': 1, 'title': 'Track 1'}]}
            (sources / 'fixture.info.json').write_text(json.dumps(metadata))
            (sources / 'incomplete.info.json').write_text('{"id":"incomplete"}')
            self.assertEqual(fetch_music.catalog(root)['added'], 1)
            self.assertEqual(fetch_music.catalog(root)['added'], 0)
            with sqlite3.connect(root / 'music/catalog.sqlite3') as db:
                rows = db.execute('SELECT title, chapters, description FROM sources').fetchall()
            self.assertEqual(len(rows), 1)
            self.assertEqual(json.loads(rows[0][1]), metadata['chapters'])
            self.assertEqual(rows[0][2], metadata['description'])


if __name__ == '__main__':
    unittest.main()
