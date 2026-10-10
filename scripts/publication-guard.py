#!/usr/bin/env python3
"""Select successful release PRs and revalidate their exact tested head."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import urllib.request

REPO = 'yantaolu/homebrew-tap'
SOURCE = 'yantaolu/codex-switch'
FORMULA = 'Formula/codex-switch.rb'
BRANCH = r'release/codex-switch-v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)'
JOBS = {'test-bot (macos-15)', 'test-bot (macos-15-intel)'}


def api(path):
    result = subprocess.run(['gh', 'api', path], check=True, capture_output=True, text=True)
    return json.loads(result.stdout)


def eligible(pr):
    return (pr['state'] == 'open' and not pr['draft'] and
            pr['head']['repo'] is not None and pr['head']['repo']['full_name'] == REPO and
            pr['base']['ref'] == 'main' and re.fullmatch(BRANCH, pr['head']['ref']))


def select(event, request=api):
    run = event['workflow_run']
    if (run['conclusion'] != 'success' or run['event'] != 'pull_request' or
            run['head_repository']['full_name'] != REPO):
        return None
    candidates = request(f'repos/{REPO}/commits/{run["head_sha"]}/pulls?per_page=100')
    candidates = [pr for pr in candidates if eligible(pr) and pr['head']['sha'] == run['head_sha']]
    if len(candidates) != 1:
        return None
    return candidates[0]['number'], run['head_sha'], run['id']


def test_run(pr, run_id=None, request=api):
    runs = request(f'repos/{REPO}/actions/workflows/tests.yml/runs?event=pull_request&head_sha={pr["head"]["sha"]}&per_page=100')['workflow_runs']
    if not runs:
        raise ValueError('No native test-bot workflow for reviewed head')
    if run_id is not None and run_id != runs[0]['id']:
        raise ValueError('A newer test run exists; wait for its completed verification')
    run_id = runs[0]['id']
    run = request(f'repos/{REPO}/actions/runs/{run_id}')
    if (run['conclusion'] != 'success' or run['event'] != 'pull_request' or
            run['head_sha'] != pr['head']['sha'] or
            run['head_repository']['full_name'] != REPO or
            run['path'] != '.github/workflows/tests.yml'):
        raise ValueError('Test run does not match the successful reviewed PR head')
    # Even a successful workflow must actually contain both successful native jobs.
    jobs = request(f'repos/{REPO}/actions/runs/{run_id}/jobs?per_page=100')['jobs']
    if not JOBS.issubset({job['name'] for job in jobs if job['conclusion'] == 'success'}):
        raise ValueError('Both native architecture jobs must succeed')
    artifacts = request(f'repos/{REPO}/actions/runs/{run_id}/artifacts?per_page=100')['artifacts']
    expected = {'bottles_macos-15', 'bottles_macos-15-intel'}
    available = {item['name'] for item in artifacts if not item['expired'] and item['size_in_bytes'] > 0}
    if not expected.issubset(available):
        raise ValueError('Missing or expired tested bottle artifacts')
    return run_id


def validate_recipe(recipe, current, request=api):
    pairs = re.findall(r'url "(https://github.com/yantaolu/codex-switch/releases/download/v([0-9]+\.[0-9]+\.[0-9]+)/codex-switch_\2_darwin_(arm64|amd64)\.tar.gz)"\n\s+sha256 "([a-f0-9]{64})"', recipe)
    if len(pairs) != 2 or {pair[2] for pair in pairs} != {'arm64', 'amd64'} or len({pair[1] for pair in pairs}) != 1:
        raise ValueError('Expected exactly two official native release URLs')
    version = pairs[0][1]
    old = re.findall(r'/releases/download/v([0-9]+\.[0-9]+\.[0-9]+)/codex-switch_', current)
    if len(set(old)) != 1 or tuple(map(int, old[0].split('.'))) > tuple(map(int, version.split('.'))):
        raise ValueError('Publication would downgrade the current formula')
    release = request(f'repos/{SOURCE}/releases/tags/v{version}')
    if release['draft'] or release['prerelease'] or release['tag_name'] != f'v{version}':
        raise ValueError('Release must be public and stable')
    assets = {item['name']: item['browser_download_url'] for item in release['assets']}
    prefix = f'https://github.com/{SOURCE}/releases/download/v{version}/'
    if assets.get('checksums.txt') != prefix + 'checksums.txt':
        raise ValueError('Missing release checksum manifest')
    with urllib.request.urlopen(assets['checksums.txt'], timeout=60) as response:
        manifest = response.read(8193)
    if len(manifest) > 8192:
        raise ValueError('Oversized checksum manifest')
    hashes = {}
    for line in manifest.decode().splitlines():
        match = re.fullmatch(r'([a-f0-9]{64})  (\S+)', line)
        if not match or match[2] in hashes:
            raise ValueError('Malformed checksum manifest')
        hashes[match[2]] = match[1]
    for url, _, arch, checksum in pairs:
        name = f'codex-switch_{version}_darwin_{arch}.tar.gz'
        if assets.get(name) != url or hashes.get(name) != checksum:
            raise ValueError('Recipe differs from published release checksums')
        with urllib.request.urlopen(url, timeout=90) as response:
            archive = response.read(128 * 1024 * 1024 + 1)
        if len(archive) > 128 * 1024 * 1024 or hashlib.sha256(archive).hexdigest() != checksum:
            raise ValueError('Public native archive checksum mismatch')
    return version


def guard(number, head, run_id=None, request=api):
    if not re.fullmatch(r'[1-9][0-9]*', str(number)) or not re.fullmatch(r'[a-f0-9]{40}', head):
        raise ValueError('Invalid PR number or head SHA')
    pr = request(f'repos/{REPO}/pulls/{number}')
    if pr['head']['repo'] is None or pr['head']['repo']['full_name'] != REPO or pr['base']['ref'] != 'main' or pr['head']['sha'] != head:
        raise ValueError('Reviewed PR head changed or comes from another repository')
    files = request(f'repos/{REPO}/pulls/{number}/files?per_page=100')
    if pr['changed_files'] != 1 or [item['filename'] for item in files] != [FORMULA]:
        raise ValueError('Publication PR must change only the formula')
    test_run(pr, run_id, request)
    recipe = base64.b64decode(request(f'repos/{REPO}/contents/{FORMULA}?ref={head}')['content']).decode()
    current = base64.b64decode(request(f'repos/{REPO}/contents/{FORMULA}?ref=main')['content']).decode()
    version = validate_recipe(recipe, current, request)
    if pr['state'] == 'open' and not eligible(pr):
        # Manually dispatched PRs can use another branch, but still get every publication guard.
        if run_id is not None:
            raise ValueError('Automatic publication requires a managed release branch')
    if re.fullmatch(BRANCH, pr['head']['ref']) and pr['head']['ref'] != f'release/codex-switch-v{version}':
        raise ValueError('Release branch does not match recipe version')
    print(f'Validated {version}, PR #{number}, head {head}')
    return pr['state'].upper()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--select', type=Path)
    parser.add_argument('--verify-recipe', type=Path)
    parser.add_argument('--pr')
    parser.add_argument('--head')
    parser.add_argument('--run-id', type=int)
    args = parser.parse_args()
    if args.verify_recipe:
        recipe = args.verify_recipe.read_text()
        print('Verified public release: ' + validate_recipe(recipe, recipe))
    elif args.select:
        result = select(json.loads(args.select.read_text()))
        if result:
            with open(os.environ['GITHUB_OUTPUT'], 'a') as output:
                output.write(f'pr={result[0]}\nhead={result[1]}\nrun_id={result[2]}\n')
    else:
        state = guard(args.pr, args.head, args.run_id)
        with open(os.environ['GITHUB_OUTPUT'], 'a') as output:
            output.write(f'state={state}\n')
