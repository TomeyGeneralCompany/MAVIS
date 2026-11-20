#!/usr/bin/env python3
"""Download music sources into MAVIS's local catalog; does not broadcast them."""
import argparse
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
from urllib.parse import urlsplit

from mavis.ffmpeg_utils import ffmpeg_path, ffprobe_path


def youtube_url(value):
    url = urlsplit(value)
    if (url.scheme != 'https' or url.hostname not in
            {'youtube.com', 'www.youtube.com', 'm.youtube.com', 'youtu.be'}
            or url.username or url.password or url.port not in (None, 443)):
        raise argparse.ArgumentTypeError('Enter an HTTPS YouTube video, playlist, or channel URL.')
    return value


def catalog(root):
    """Recover downloaded files into the catalog, including interrupted prior runs."""
    music = Path(root) / 'music'
    music.mkdir(parents=True, exist_ok=True)
    added = 0
    with sqlite3.connect(music / 'catalog.sqlite3') as db:
        db.execute('CREATE TABLE IF NOT EXISTS sources '
                   '(id TEXT PRIMARY KEY, title TEXT, channel TEXT, source_url TEXT, '
                   'file TEXT, duration REAL, chapters TEXT, description TEXT)')
        for metadata in sorted((music / 'sources').glob('*.info.json')):
            audio = metadata.with_name(metadata.name.removesuffix('.info.json') + '.m4a')
            if not audio.is_file():
                continue
            try:
                info = json.loads(metadata.read_text(encoding='utf-8'))
                result = subprocess.run([ffprobe_path(), '-v', 'error', '-show_format',
                    '-show_streams', '-of', 'json', str(audio)], check=True,
                    capture_output=True, text=True, timeout=30)
                probe = json.loads(result.stdout)
                duration = float(probe['format']['duration'])
                if duration <= 0 or not any(s.get('codec_type') == 'audio'
                                           for s in probe['streams']):
                    raise ValueError('No playable audio')
                identity = str(info['id'])
                previous = db.execute('SELECT 1 FROM sources WHERE id=?', (identity,)).fetchone()
                db.execute('INSERT OR REPLACE INTO sources VALUES (?,?,?,?,?,?,?,?)', (
                    identity, info.get('title', identity), info.get('channel', ''),
                    info.get('webpage_url', ''), str(audio.relative_to(root)), duration,
                    json.dumps(info.get('chapters') or [], ensure_ascii=False),
                    info.get('description', '')))
                added += previous is None
            except (ValueError, KeyError, OSError, subprocess.SubprocessError) as exc:
                print(f'Skipping invalid audio {audio.name}: {exc}', file=sys.stderr)
        count, seconds = db.execute('SELECT COUNT(*), COALESCE(SUM(duration),0) FROM sources').fetchone()
    return {'added': added, 'sources': count, 'minutes': round(seconds / 60, 2),
            'catalog': str(music / 'catalog.sqlite3')}


def fetch(root, urls, limit=10, collection=False):
    """Download a bounded batch sequentially, resuming and deduplicating by video ID."""
    if not 1 <= limit <= 200:
        raise ValueError('Limit must be between 1 and 200.')
    urls = [youtube_url(url) for url in urls]
    root = Path(root).expanduser().resolve()
    sources = root / 'music' / 'sources'
    sources.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, '-m', 'yt_dlp', '--ignore-config', '--no-plugin-dirs',
        '--ignore-errors', '--continue', '--no-overwrites', '--no-progress',
        '--retries', '3', '--fragment-retries', '3', '--socket-timeout', '30',
        '--playlist-end', str(limit), '--match-filter', '!is_live & !is_upcoming',
        '--yes-playlist' if collection else '--no-playlist',
        '--download-archive', str(root / 'music' / 'downloaded.txt'),
        '--write-info-json', '--no-clean-info-json',
        '--ffmpeg-location', str(Path(ffmpeg_path()).parent),
        '-f', 'bestaudio/best', '-x', '--audio-format', 'm4a', '--audio-quality', '192K',
        '-o', str(sources / '%(id)s.%(ext)s'), '--', *urls]
    if shutil.which('node'):
        command[3:3] = ['--js-runtimes', 'node']
    result = subprocess.run(command, check=False)
    report = catalog(root)
    report['download_exit_code'] = result.returncode
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('urls', nargs='*', type=youtube_url)
    parser.add_argument('--root', type=Path, default=Path(os.environ.get(
        'TUBE_WORKSPACE', Path.home() / '.local/share/mavis/workspace')))
    parser.add_argument('--limit', type=int, default=10,
                        help='Maximum playlist entries examined per source (1–200).')
    parser.add_argument('--collection', action='store_true', help='Import a playlist or channel batch.')
    parser.add_argument('--status', action='store_true', help='Reconcile local audio and show catalog totals.')
    args = parser.parse_args()
    if not args.status and not args.urls:
        parser.error('Supply a YouTube URL or --status.')
    report = catalog(args.root.expanduser().resolve()) if args.status else fetch(
        args.root, args.urls, args.limit, args.collection)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 1 if report.get('download_exit_code') else 0


if __name__ == '__main__':
    raise SystemExit(main())
