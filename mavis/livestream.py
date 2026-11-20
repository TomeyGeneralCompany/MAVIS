"""Personal continuous programming: buffered local generation and RTMP transport."""
from collections import deque
import os
from pathlib import Path
import secrets
import signal
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from urllib.parse import urlsplit

from mavis.activation import require_activation
from mavis.ffmpeg_utils import ffmpeg_path, ffprobe_path
from mavis.platform_support import runner_busy
from mavis.shorts import probe, validate_short

SOURCE = Path(__file__).resolve().parents[1]


def destination(server, key):
    server, key = str(server).strip(), str(key).strip()
    url = urlsplit(server)
    if (url.scheme not in ('rtmp', 'rtmps') or not url.hostname or url.username
            or url.password or url.query or url.fragment or any(c.isspace() for c in server)):
        raise ValueError('Enter an RTMP or RTMPS server URL without credentials or a query.')
    if not key or len(key) > 1000 or any(ord(c) < 33 or ord(c) > 126 for c in key):
        raise ValueError('Enter a valid stream key.')
    url.port  # Validate the optional port before starting any processes.
    return server.rstrip('/') + '/' + key


def process_options():
    return ({'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW}
            if os.name == 'nt' else {'start_new_session': True})


def terminate(process):
    if process is None or process.poll() is not None:
        return
    try:
        if os.name == 'nt':
            subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
        else:
            os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        try:
            if os.name != 'nt':
                os.killpg(process.pid, signal.SIGKILL)
            else:
                process.kill()
            process.wait(timeout=5)
        except (OSError, subprocess.TimeoutExpired):
            pass


def segment_command(path, offset, layout='landscape', realtime=True):
    width, height = (1280, 720) if layout == 'landscape' else (720, 1280)
    return [ffmpeg_path(), '-hide_banner', '-nostdin', '-loglevel', 'error',
            *(['-re'] if realtime else []), '-i', str(path),
            '-map', '0:v:0', '-map', '0:a:0',
            '-vf', f'scale={width}:{height}:force_original_aspect_ratio=decrease:force_divisible_by=2,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1',
            '-r', '30', '-c:v', 'libx264', '-preset', 'ultrafast', '-tune', 'zerolatency',
            '-threads', '1', '-pix_fmt', 'yuv420p', '-g', '60', '-keyint_min', '60',
            '-sc_threshold', '0', '-bf', '0', '-b:v', '2500k', '-maxrate', '2500k',
            '-bufsize', '5000k', '-c:a', 'aac', '-b:a', '128k', '-ar', '48000', '-ac', '2',
            '-output_ts_offset', f'{offset:.6f}', '-mpegts_copyts', '1',
            '-muxdelay', '0', '-muxpreload', '0', '-flush_packets', '1', '-f', 'mpegts', 'pipe:1']


def sink_command(target):
    return [ffmpeg_path(), '-hide_banner', '-nostdin', '-loglevel', 'error',
            '-fflags', '+genpts', '-copyts', '-start_at_zero', '-f', 'mpegts',
            '-probesize', '32768', '-analyzeduration', '1000000', '-i', 'pipe:0',
            '-map', '0:v:0', '-map', '0:a:0', '-c', 'copy',
            '-flvflags', 'no_duration_filesize', '-flush_packets', '1', '-rw_timeout', '15000000', '-f', 'flv', target]


class LiveSession:
    def __init__(self, root):
        self.root = Path(root)
        self.condition = threading.Condition(threading.RLock())
        self.queue = deque()
        self.history = deque(maxlen=3)
        self.halt = threading.Event()
        self.halt.set()
        self.threads = []
        self.children = {}
        self.state = {'state': 'Stopped', 'generated': 0, 'played': 0, 'repeats': 0,
                      'queue': 0, 'on_air': None, 'producing': None, 'error': None}
        self.target = ''
        self.key = ''

    def status(self):
        with self.condition:
            result = dict(self.state, queue=len(self.queue), running=not self.halt.is_set())
            job = result.get('producing')
            if job:
                import json
                try:
                    checkpoint = json.loads((self.root / 'runs' / job / 'checkpoint.json').read_text())
                    result['production_stage'] = checkpoint.get('stage')
                except (OSError, ValueError):
                    pass
            return result

    def _set(self, **changes):
        with self.condition:
            self.state.update(changes)
            self.condition.notify_all()

    def _safe_error(self, error):
        return str(error).replace(self.target, '[stream destination]').replace(self.key, '[stream key]') if self.key else str(error)

    def _spawn(self, role, command, **kwargs):
        with self.condition:
            if self.halt.is_set():
                raise InterruptedError('Stream stopped.')
            process = subprocess.Popen(command, **process_options(), **kwargs)
            self.children[role] = process
            return process

    def start(self, data):
        require_activation(self.root)
        target = destination(data.get('server', ''), data.get('key', ''))
        topics = [t.strip() for t in str(data.get('topics', '')).splitlines() if t.strip()]
        if not topics or len(topics) > 50 or any(len(t) > 2000 for t in topics):
            raise ValueError('Enter 1–50 topics, one per line, up to 2000 characters each.')
        buffer = data.get('buffer', 2)
        if type(buffer) is not int or not 1 <= buffer <= 10:
            raise ValueError('Choose a starting buffer from 1 to 10 segments.')
        layout = data.get('layout', 'landscape')
        if layout not in ('landscape', 'portrait'):
            raise ValueError('Choose landscape or portrait.')
        ffmpeg_path()
        ffprobe_path()
        if 'research' in data and type(data['research']) is not bool:
            raise ValueError('Research must be enabled or disabled.')
        with self.condition:
            if not self.halt.is_set() or any(t.is_alive() for t in self.threads):
                raise ValueError('A livestream is already running or stopping.')
            self.root.mkdir(parents=True, exist_ok=True)
            self.target, self.key = target, str(data['key']).strip()
            self.topics, self.buffer, self.layout = topics, buffer, layout
            self.research = bool(data.get('research', True))
            self.queue.clear()
            self.history.clear()
            self.children.clear()
            self.halt.clear()
            self.state = {'state': 'Buffering', 'generated': 0, 'played': 0, 'repeats': 0,
                          'on_air': None, 'producing': None, 'error': None, 'buffer_target': buffer,
                          'channel': str(data.get('channel', '')).strip()[:200]}
            self.session = secrets.token_hex(6)
            self.threads = [threading.Thread(target=self._producer, daemon=True),
                            threading.Thread(target=self._consumer, daemon=True),
                            threading.Thread(target=self._activation_watch, daemon=True)]
            for thread in self.threads:
                thread.start()
        return self.status()

    def stop(self):
        self.halt.set()
        with self.condition:
            self.condition.notify_all()
            processes = list(self.children.values())
        for process in processes:
            terminate(process)
        for thread in self.threads:
            if thread is not threading.current_thread():
                thread.join(timeout=15)
        self._set(state='Stopped', on_air=None, on_air_title=None, producing=None, production_topic=None)
        self.target = self.key = ''
        return self.status()

    def _activation_watch(self):
        while not self.halt.wait(1):
            try:
                require_activation(self.root)
            except Exception as exc:
                self._set(error=self._safe_error(exc))
                self.stop()
                return

    def _producer(self):
        index = 0
        while not self.halt.is_set():
            with self.condition:
                if len(self.queue) >= self.buffer + 2:
                    self.condition.wait(timeout=1)
                    continue
            if runner_busy(self.root):
                self._set(production_stage='Waiting for another production job')
                self.halt.wait(1)
                continue
            if shutil.disk_usage(self.root).free < 1024**3:
                self._set(production_stage='Waiting for free disk space')
                self.halt.wait(5)
                continue
            job = f'live-{self.session}-{index:06d}'
            folder = self.root / 'runs' / job
            folder.mkdir(parents=True, exist_ok=True)
            self._set(producing=job, production_topic=self.topics[index % len(self.topics)], production_stage='Starting')
            try:
                require_activation(self.root)
                env = {**os.environ, 'TUBE_WORKSPACE': str(self.root),
                       'TUBE_OFFLINE': '0' if self.research else '1', 'PYTHONUNBUFFERED': '1'}
                command = [sys.executable, '-X', 'utf8', str(SOURCE / 'run_mavis.py'),
                           'run', '--job-id', job, '--topic', self.topics[index % len(self.topics)]]
                with (folder / 'production.log').open('ab') as log:
                    process = self._spawn('production', command, env=env, stdout=log, stderr=subprocess.STDOUT)
                    while process.poll() is None and not self.halt.wait(.25):
                        pass
                if self.halt.is_set():
                    break
                import json
                checkpoint = json.loads((folder / 'checkpoint.json').read_text())
                if process.returncode or not checkpoint.get('complete'):
                    raise RuntimeError(checkpoint.get('error') or 'Segment production failed; see production.log.')
                video = folder / 'short.mp4'
                validate_short(video)
                with self.condition:
                    self.queue.append(video)
                    self.state['generated'] += 1
                    self.state['production_stage'] = 'Queued'
                    self.state['producing'] = None
                    self.state['production_topic'] = None
                    self.condition.notify_all()
                index += 1
            except InterruptedError:
                break
            except Exception as exc:
                self._set(error=self._safe_error(exc), production_stage='Retrying segment in 15 seconds')
                self.halt.wait(15)
        self._set(producing=None)

    def _next(self):
        with self.condition:
            if self.queue:
                path = self.queue.popleft()
                self.history.append(path)
                self.condition.notify_all()
                return path, False
            if self.history:
                self.history.rotate(-1)
                return self.history[-1], True
            return None, False

    def _consumer(self):
        with self.condition:
            while len(self.queue) < self.buffer and not self.halt.is_set():
                self.condition.wait(timeout=.5)
        delay = 1
        while not self.halt.is_set():
            try:
                self._broadcast()
                return
            except InterruptedError:
                return
            except Exception as exc:
                if not self.halt.is_set():
                    self._set(state='Reconnecting', error=self._safe_error(exc), on_air=None, on_air_title=None)
                    self.halt.wait(delay)
                    delay = min(30, delay * 2)

    def _broadcast(self):
        sink = converter = None
        with tempfile.TemporaryFile() as errors:
            try:
                sink = self._spawn('broadcast', sink_command(self.target), stdin=subprocess.PIPE,
                                   stdout=subprocess.DEVNULL, stderr=errors)
                offset = 0.0
                while not self.halt.is_set():
                    require_activation(self.root)
                    path, replay = self._next()
                    if path is None:
                        raise RuntimeError('No buffered segment is available.')
                    duration = float(probe(path)['format']['duration'])
                    import json
                    try:
                        title = json.loads((path.parent / 'checkpoint.json').read_text()).get('content', {}).get('title')
                    except (OSError, ValueError):
                        title = None
                    self._set(state='Replaying buffer' if replay else 'Broadcasting', on_air=path.parent.name, on_air_title=title)
                    with tempfile.TemporaryFile() as segment_errors:
                        converter = self._spawn('segment', segment_command(path, offset, self.layout),
                                                stdout=subprocess.PIPE, stderr=segment_errors)
                        while not self.halt.is_set():
                            if sink.poll() is not None:
                                raise RuntimeError('Broadcast connection closed.')
                            block = converter.stdout.read1(32768)
                            if not block:
                                break
                            sink.stdin.write(block)
                            sink.stdin.flush()
                        converter.stdout.close()
                        code = converter.wait(timeout=15)
                        if code and not self.halt.is_set():
                            segment_errors.seek(0)
                            raise RuntimeError(segment_errors.read().decode(errors='replace')[-1500:])
                    if self.halt.is_set():
                        break
                    offset += duration
                    with self.condition:
                        self.state['played'] += 1
                        self.state['repeats'] += int(replay)
                if sink.stdin:
                    try:
                        sink.stdin.close()
                    except OSError:
                        pass
            except Exception as exc:
                errors.seek(0)
                detail = errors.read().decode(errors='replace')[-1500:]
                raise RuntimeError(self._safe_error(detail or exc)) from None
            finally:
                terminate(converter)
                terminate(sink)
