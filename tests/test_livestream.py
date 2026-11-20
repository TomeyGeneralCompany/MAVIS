"""Personal livestream controls, stream-key handling and real FFmpeg continuity."""
import json
from pathlib import Path
import re
import shutil
import subprocess
import socket
import sys
import time
from types import SimpleNamespace
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from mavis import livestream as live
from mavis.activation import ActivationRequired
from mavis.ffmpeg_utils import ffmpeg_path
from mavis.shorts import probe


class LiveTests(unittest.TestCase):
    def test_destination_validation_and_secret_redaction(self):
        self.assertEqual(live.destination('rtmps://example.test/live/', 'secret-key'),
                         'rtmps://example.test/live/secret-key')
        for server, key in [('https://example.test', 'key'), ('rtmp://user:pass@example.test/live', 'key'),
                            ('rtmp://example.test/live?token=x', 'key'), ('rtmp://example.test', 'bad\nkey'),
                            ('rtmp://example.test', '')]:
            with self.subTest(server=server), self.assertRaises(ValueError):
                live.destination(server, key)
        session = live.LiveSession(Path('/unused'))
        session.target, session.key = 'rtmps://example.test/live/secret-key', 'secret-key'
        self.assertNotIn('secret-key', session._safe_error('failed: ' + session.target))
        self.assertNotIn('secret-key', json.dumps(session.status()))

    def test_new_segments_take_priority_then_history_replays(self):
        session = live.LiveSession(Path('/unused'))
        a, b = Path('a.mp4'), Path('b.mp4')
        session.queue.extend([a, b])
        self.assertEqual(session._next(), (a, False))
        self.assertEqual(session._next(), (b, False))
        self.assertEqual(session._next(), (a, True))
        self.assertEqual(session._next(), (b, True))
        session.queue.append(Path('fresh.mp4'))
        self.assertEqual(session._next(), (Path('fresh.mp4'), False))

    def test_stopped_sessions_do_not_start_children(self):
        session = live.LiveSession(Path('/unused'))
        with self.assertRaises(InterruptedError):
            session._spawn('test', ['unused'])

    def test_local_http_controls_require_token_and_activation(self):
        from local_studio import Studio, serve
        with tempfile.TemporaryDirectory() as folder, patch('local_studio.require_activation'):
            studio = Studio(Path(folder))
            with serve(studio, 0) as server:
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                base = f'http://127.0.0.1:{server.server_port}'
                try:
                    page = urlopen(base).read().decode()
                    self.assertIn('Personal livestream', page)
                    token = re.search(r"'X-Studio-Token':'([^']+)'", page)[1]
                    self.assertEqual(json.load(urlopen(base + '/live'))['state'], 'Stopped')
                    request = Request(base + '/live/start', data=b'{}', headers={'X-Studio-Token': 'wrong'})
                    with self.assertRaises(HTTPError) as error:
                        urlopen(request)
                    self.assertEqual(error.exception.code, 403)
                    with patch.object(studio.live, 'start', return_value={'state': 'Buffering'}) as start:
                        data = {'server': 'rtmps://example.test/live', 'key': 'secret', 'topics': 'Tools', 'buffer': 2}
                        request = Request(base + '/live/start', data=json.dumps(data).encode(),
                                          headers={'X-Studio-Token': token})
                        self.assertEqual(json.load(urlopen(request))['state'], 'Buffering')
                        start.assert_called_once_with(data)
                    request = Request(base + '/live/stop', data=b'{}', headers={'X-Studio-Token': token})
                    self.assertEqual(json.load(urlopen(request))['state'], 'Stopped')
                    with patch('local_studio.require_activation', side_effect=ActivationRequired('Locked')):
                        with self.assertRaises(HTTPError) as error:
                            urlopen(base + '/live')
                        self.assertEqual(error.exception.code, 403)
                finally:
                    server.shutdown()
                    thread.join()

    def test_producer_routes_through_normal_local_pipeline_without_upload(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            session = live.LiveSession(root)
            session.halt.clear()
            session.topics, session.buffer, session.session, session.research = ['Tool care'], 1, 'test', True
            commands = []
            def generate(role, command, **kwargs):
                commands.append((command, kwargs))
                job = command[command.index('--job-id') + 1]
                run = root / 'runs' / job
                (run / 'checkpoint.json').write_text(json.dumps({'complete': True}))
                (run / 'short.mp4').write_bytes(b'validated media')
                return SimpleNamespace(returncode=0, poll=lambda: 0)
            with patch.object(session, '_spawn', side_effect=generate), patch.object(live, 'validate_short'), \
                 patch.object(live, 'require_activation'), patch.object(live, 'runner_busy', return_value=False):
                thread = threading.Thread(target=session._producer)
                thread.start()
                limit = time.monotonic() + 5
                while not session.status()['generated'] and time.monotonic() < limit:
                    time.sleep(.01)
                session.halt.set()
                with session.condition:
                    session.condition.notify_all()
                thread.join(timeout=3)
            self.assertFalse(thread.is_alive())
            self.assertTrue(commands)
            command, options = commands[0]
            self.assertIn(str(live.SOURCE / 'run_mavis.py'), command)
            self.assertEqual(command[-2:], ['--topic', 'Tool care'])
            self.assertNotIn('--upload-private', command)
            self.assertEqual(options['env']['TUBE_WORKSPACE'], str(root))
            self.assertEqual(options['env']['TUBE_OFFLINE'], '0')
            self.assertGreaterEqual(session.status()['generated'], 1)

    def test_reconnect_retries_without_leaking_the_stream_key(self):
        session = live.LiveSession(Path('/unused'))
        session.halt.clear()
        session.buffer = 1
        session.queue.append(Path('buffered.mp4'))
        session.target, session.key = 'rtmps://example.test/live/secret', 'secret'
        attempts = []
        def broadcast():
            attempts.append(1)
            if len(attempts) == 1:
                raise OSError('Connection failed: ' + session.target)
            session.halt.set()
        with patch.object(session, '_broadcast', side_effect=broadcast):
            session._consumer()
        self.assertEqual(len(attempts), 2)
        self.assertNotIn('secret', session.status()['error'])

    def test_stop_terminates_owned_processes(self):
        with tempfile.TemporaryDirectory() as folder:
            session = live.LiveSession(Path(folder))
            session.halt.clear()
            child = session._spawn('production', [sys.executable, '-c', 'import time; time.sleep(60)'])
            self.assertIsNone(child.poll())
            self.assertEqual(session.stop()['state'], 'Stopped')
            self.assertIsNotNone(child.poll())
            self.assertFalse(session.status()['running'])

    def test_real_rtmp_push_reaches_local_receiver(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with socket.socket() as reservation:
                reservation.bind(('127.0.0.1', 0))
                port = reservation.getsockname()[1]
            url = f'rtmp://127.0.0.1:{port}/live/test'
            received = root / 'received.flv'
            with tempfile.TemporaryFile() as errors:
                receiver = subprocess.Popen([ffmpeg_path(), '-y', '-hide_banner', '-loglevel', 'error',
                    '-listen', '1', '-i', url, '-c', 'copy', '-f', 'flv', str(received)],
                    stdout=subprocess.DEVNULL, stderr=errors, **live.process_options())
                sender = None
                try:
                    time.sleep(.5)
                    sender = subprocess.Popen(live.sink_command(url), stdin=subprocess.PIPE,
                                              stdout=subprocess.DEVNULL, stderr=errors,
                                              **live.process_options())
                    # Real MPEG-TS input and actual RTMP network transport, all on loopback.
                    packet = subprocess.check_output([ffmpeg_path(), '-v', 'error',
                        '-f', 'lavfi', '-i', 'color=c=teal:s=320x180:r=30',
                        '-f', 'lavfi', '-i', 'sine=sample_rate=48000', '-t', '2',
                        '-c:v', 'libx264', '-preset', 'ultrafast', '-threads', '1',
                        '-bf', '0', '-c:a', 'aac', '-f', 'mpegts', 'pipe:1'])
                    sender.stdin.write(packet)
                    sender.stdin.close()
                    self.assertEqual(sender.wait(timeout=20), 0)
                    receiver.wait(timeout=20)
                    self.assertTrue(received.is_file())
                    self.assertEqual({s['codec_type'] for s in probe(received)['streams']}, {'video', 'audio'})
                finally:
                    live.terminate(sender)
                    live.terminate(receiver)

    def test_real_media_transitions_keep_audio_video_and_timestamps(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            clips = []
            for index, (color, seconds) in enumerate([('red', '1.2'), ('blue', '1.6')]):
                path = root / f'{index}.mp4'
                subprocess.run([ffmpeg_path(), '-y', '-v', 'error', '-f', 'lavfi', '-i',
                                f'color=c={color}:s=320x180:r=30', '-f', 'lavfi', '-i',
                                'sine=frequency=440:sample_rate=48000', '-t', seconds,
                                '-c:v', 'libx264', '-preset', 'ultrafast', '-threads', '1',
                                '-c:a', 'aac', str(path)], check=True, capture_output=True)
                clips.append(path)
            output = root / 'continuous.flv'
            with tempfile.TemporaryFile() as errors:
                sink = subprocess.Popen(live.sink_command(str(output)), stdin=subprocess.PIPE,
                                        stdout=subprocess.DEVNULL, stderr=errors, **live.process_options())
                try:
                    offset = 0
                    for path in [clips[0], clips[1], clips[0]]:
                        segment = subprocess.Popen(live.segment_command(path, offset, realtime=False),
                                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                                   **live.process_options())
                        packet, error = segment.communicate(timeout=30)
                        self.assertEqual(segment.returncode, 0, error.decode(errors='replace'))
                        sink.stdin.write(packet)
                        offset += float(probe(path)['format']['duration'])
                    sink.stdin.close()
                    self.assertEqual(sink.wait(timeout=30), 0)
                finally:
                    live.terminate(sink)
                errors.seek(0)
                self.assertNotIn('Non-monoton', errors.read().decode())
            result = probe(output)
            video = next(s for s in result['streams'] if s['codec_type'] == 'video')
            audio = next(s for s in result['streams'] if s['codec_type'] == 'audio')
            self.assertEqual((video['width'], video['height'], video['codec_name']), (1280, 720, 'h264'))
            self.assertEqual((audio['codec_name'], audio['sample_rate'], audio['channels']), ('aac', '48000', 2))
            self.assertAlmostEqual(float(result['format']['duration']), 4, delta=.15)
            from mavis.ffmpeg_utils import ffprobe_path
            packets = json.loads(subprocess.check_output([ffprobe_path(), '-v', 'error', '-show_packets',
                '-show_entries', 'packet=stream_index,dts_time', '-of', 'json', str(output)]))['packets']
            for stream in (0, 1):
                stamps = [float(p['dts_time']) for p in packets if p['stream_index'] == stream and 'dts_time' in p]
                self.assertTrue(all(b >= a for a, b in zip(stamps, stamps[1:])))
                self.assertLess(max(b-a for a, b in zip(stamps, stamps[1:])), .1)

if __name__ == '__main__':
    unittest.main()
