#!/usr/bin/env python3
"""Upload missing bottles; never replace an existing release asset."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import urllib.request

REPO = 'yantaolu/homebrew-tap'


def gh(*args):
    return subprocess.run(['gh', *args], check=True, capture_output=True, text=True).stdout


def publish(directory, check_only=False):
    metadata = list(directory.glob('*.bottle.json'))
    if len(metadata) != 1:
        raise ValueError('Expected one merged bottle metadata file')
    recipes = json.loads(metadata[0].read_text())
    if len(recipes) != 1 or next(iter(recipes)) not in {'codex-switch', 'yantaolu/tap/codex-switch'}:
        raise ValueError('Only codex-switch bottles may be published')
    recipe = next(iter(recipes.values()))
    bottle = recipe['bottle']
    prefix = f'https://github.com/{REPO}/releases/download/codex-switch-'
    version = recipe['formula']['pkg_version']
    if not re.fullmatch(r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)', version):
        raise ValueError('Unexpected bottle version')
    if bottle['root_url'] != prefix + version:
        raise ValueError('Unexpected bottle release URL')
    tags = bottle['tags']
    if set(tags) != {'arm64_sequoia', 'sequoia'}:
        raise ValueError('Both supported macOS architecture bottles are required')
    files = []
    for item in tags.values():
        filename = item['filename']
        local_name = item['local_filename']
        if Path(filename).name != filename or Path(local_name).name != local_name:
            raise ValueError('Unsafe bottle filename')
        path = directory / local_name
        if hashlib.sha256(path.read_bytes()).hexdigest() != item['sha256']:
            raise ValueError('Local bottle checksum mismatch')
        files.append((path, filename, item['sha256']))
    tag = f'codex-switch-{version}'
    # List by tag through the refs API: no broad exception handling around network failures.
    refs = json.loads(gh('api', f'repos/{REPO}/git/matching-refs/tags/{tag}'))
    if not any(item['ref'] == f'refs/tags/{tag}' for item in refs):
        if check_only:
            raise ValueError('Bottle release does not exist')
        gh('release', 'create', tag, '--repo', REPO, '--target', 'main', '--title',
           f'codex-switch {version} bottles', '--notes', 'Homebrew bottles from the tested native release PR.')
    release = json.loads(gh('api', f'repos/{REPO}/releases/tags/{tag}'))
    if release['draft'] or release['prerelease']:
        raise ValueError('Bottle release must be public and stable')
    existing = {item['name']: item['browser_download_url'] for item in release['assets']}
    # Check all existing assets before uploading any missing assets.
    for _, name, checksum in files:
        if name in existing:
            if existing[name] != bottle['root_url'] + '/' + name:
                raise ValueError('Unexpected existing bottle URL')
            with urllib.request.urlopen(existing[name], timeout=90) as response:
                digest = hashlib.sha256(response.read()).hexdigest()
            if digest != checksum:
                raise ValueError('Existing bottle differs; refusing replacement')
    for path, name, _ in files:
        if name not in existing:
            if check_only:
                raise ValueError('Bottle asset has not been published')
            upload = directory / name
            if path != upload:
                shutil.copyfile(path, upload)
            gh('release', 'upload', tag, str(upload), '--repo', REPO)
        print(f'{name}: published or already identical')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    publish(args.directory, args.check_only)
