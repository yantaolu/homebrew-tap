#!/usr/bin/env python3
"""Verify a published formula still matches its review and public bottles."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import urllib.request

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--reviewed', type=Path, required=True)
parser.add_argument('--info', type=Path, required=True)
args = parser.parse_args()

current = Path('Formula/codex-switch.rb').read_text()
without_bottle = re.sub(r'(?ms)^  bottle do\n.*?^  end\n\n?', '', current)
if without_bottle.strip() != args.reviewed.read_text().strip():
    raise SystemExit('Published recipe differs from reviewed PR beyond the bottle block')

formula = json.loads(args.info.read_text())['formulae'][0]
version = formula['versions']['stable']
files = formula['bottle']['stable']['files']
repository = os.environ.get('GITHUB_REPOSITORY', 'yantaolu/homebrew-tap')
prefix = f'https://github.com/{repository}/releases/download/codex-switch-{version}/'
for tag in ('arm64_sequoia', 'sequoia'):
    item = files[tag]
    if not item['url'].startswith(prefix):
        raise SystemExit(f'Unexpected bottle URL for {tag}')
    with urllib.request.urlopen(item['url'], timeout=60) as response:
        digest = hashlib.sha256(response.read()).hexdigest()
    if digest != item['sha256']:
        raise SystemExit(f'Public bottle checksum mismatch for {tag}')
    print(f'{tag}: public SHA-256 verified')
