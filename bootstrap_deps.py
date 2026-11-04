"""Fetch immutable OpenHarmony sources and apply the recorded macOS port.

Existing checkouts must be at the pinned revision and contain exactly our patch;
local changes are never reset or overwritten. --reference-root is an optional
local source cache used to test recovery without downloading another copy.
"""
import argparse
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent
CORE = ROOT / 'vendor/runtime_core/static_core'
REVISIONS = json.loads((ROOT / 'source-revisions.json').read_text())
PATCHES = {
    'runtime_core': 'macos-port.patch',
    'ets_frontend': 'frontend-appleclang.patch',
    'third_party/vixl': 'vixl-macos.patch',
}


def git(dest, *args, **kwargs):
    return subprocess.run(['git', '-C', str(dest), *args], check=True,
                          capture_output=True, **kwargs).stdout


def destination(name):
    if name.startswith('third_party/'):
        return CORE / name
    return ROOT / 'vendor' / name


def verify_patch(dest, patch):
    """Compare the entire working diff against a patched temporary Git index."""
    handle, index = tempfile.mkstemp(prefix='arkts-index-')
    os.close(handle)
    os.unlink(index)  # read-tree creates a real index, not an empty file.
    environment = dict(os.environ, GIT_INDEX_FILE=index)
    try:
        git(dest, 'read-tree', 'HEAD', env=environment)
        git(dest, 'apply', '--cached', str(patch), env=environment)
        expected = git(dest, 'diff', '--cached', '--name-only', '--diff-filter=A',
                       env=environment).decode().splitlines()
        for name in expected:
            if not (dest / name).is_file():
                raise RuntimeError(f'Missing patched source: {dest / name}')
            git(dest, 'add', '--intent-to-add', '--', name, env=environment)
        git(dest, 'diff', '--exit-code', env=environment)
        untracked = git(dest, 'ls-files', '--others', '--exclude-standard').decode().splitlines()
        if set(untracked) - set(expected):
            raise RuntimeError(f'Unexpected local files in {dest}: {untracked}')
    finally:
        Path(index).unlink(missing_ok=True)
        Path(index + '.lock').unlink(missing_ok=True)


def fetch(name, url, reference_root, verify_only):
    dest = destination(name)
    revision = REVISIONS[name]
    if not (dest / '.git').exists():
        if verify_only:
            raise RuntimeError(f'Missing checkout: {dest}')
        if dest.exists() and any(dest.iterdir()):
            raise RuntimeError(f'Refusing to overwrite nonempty directory: {dest}')
        dest.mkdir(parents=True, exist_ok=True)
        git(dest, 'init')
        git(dest, 'remote', 'add', 'origin', url)
        source = url
        if reference_root:
            cached = (reference_root / 'runtime_core/static_core' / name
                      if name.startswith('third_party/') else reference_root / name)
            if not (cached / '.git').exists():
                raise RuntimeError(f'Missing reference checkout: {cached}')
            source = str(cached)
        print(f'Fetching {name} @ {revision[:12]}', flush=True)
        git(dest, 'fetch', '--depth=1', source, revision, timeout=600)
        git(dest, 'checkout', '--detach', revision)
    actual = git(dest, 'rev-parse', 'HEAD').decode().strip()
    if actual != revision:
        raise RuntimeError(f'{name}: expected {revision}, found {actual}; refusing reset')
    if git(dest, 'diff', '--cached', '--name-only').strip():
        raise RuntimeError(f'{name}: staged changes present; refusing to proceed')
    patch_name = PATCHES.get(name)
    if patch_name:
        patch = ROOT / 'native' / patch_name
        if not git(dest, 'status', '--porcelain', '--untracked-files=all').strip():
            if verify_only:
                raise RuntimeError(f'{name}: macOS patch has not been applied')
            git(dest, 'apply', '--check', str(patch))
            git(dest, 'apply', str(patch))
        verify_patch(dest, patch)
    elif git(dest, 'status', '--porcelain', '--untracked-files=all').strip():
        raise RuntimeError(f'{name}: unexpected local source changes')
    print(f'Verified {name} @ {revision[:12]}', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify', action='store_true', help='verify without network or patching')
    parser.add_argument('--reference-root', type=Path, help='optional local cache containing runtime_core and ets_frontend')
    args = parser.parse_args()
    (ROOT / 'build').mkdir(exist_ok=True)
    (ROOT / 'results').mkdir(exist_ok=True)
    hashes = json.loads((ROOT / 'patch-sha256.json').read_text())
    for name, expected in hashes.items():
        if hashlib.sha256((ROOT / 'native' / name).read_bytes()).hexdigest() != expected:
            raise RuntimeError(f'Patch checksum mismatch: {name}')
    upstream = {
        'runtime_core': 'https://github.com/openharmony/arkcompiler_runtime_core.git',
        'ets_frontend': 'https://github.com/openharmony/arkcompiler_ets_frontend.git',
    }
    for name, url in upstream.items():
        fetch(name, url, args.reference_root, args.verify)
    dependencies = {}
    for line in (CORE / 'scripts/third-party-lists/public').read_text().splitlines():
        if not line.strip() or line.startswith('#'):
            continue
        name, url, *_ = line.strip().split(',')
        key = 'third_party/' + name
        if key in REVISIONS:
            dependencies[key] = url.replace('https://gitcode.com/openharmony/',
                                            'https://github.com/openharmony/')
    if set(dependencies) != set(REVISIONS) - set(upstream):
        raise RuntimeError('Pinned dependencies do not match upstream manifest')
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(fetch, name, url, args.reference_root, args.verify)
                   for name, url in dependencies.items()]
        for future in concurrent.futures.as_completed(futures):
            future.result()
    receipt = {'revisions': REVISIONS, 'patch_sha256': hashes}
    (ROOT / 'build/source-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print('All pinned sources and complete macOS patches verified.', flush=True)


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, subprocess.CalledProcessError) as error:
        if isinstance(error, subprocess.CalledProcessError):
            print(error.stderr.decode(errors='replace'))
        raise SystemExit(str(error))
