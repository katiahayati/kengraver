#!/usr/bin/env python3
"""Install the tested Linux toolchain locally, or inspect it without network access."""
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import shutil
import subprocess
import tempfile
import urllib.request

PACKAGE = Path(__file__).resolve().parents[1]


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def check(root, manifest):
    rows = []
    for item in manifest['downloads']:
        probe, archive = root / item['probe'], root / 'downloads' / item['file']
        checked = probe if item['kind'] == 'data' else archive
        rows.append(dict(name=item['name'], installed=probe.exists(),
                         checksum='pass' if checked.exists() and digest(checked) == item['sha256'] else 'missing or mismatch'))
    for package in ('lxml', 'PyMuPDF'):
        try:
            version = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            version = None
        rows.append(dict(python_package=package, installed=version is not None, version=version))
    report = dict(tools=str(root), checks=rows,
                  status='pass' if all(r['installed'] and r.get('checksum', 'pass') == 'pass' for r in rows) else 'FAIL',
                  limitation='Checks archive/data hashes and installed entrypoints; use render/OMR smoke tests to verify runtime libraries.')
    print(json.dumps(report, indent=2))
    return report['status'] == 'pass'


def install(root, manifest):
    if platform.system() != 'Linux' or platform.machine() != 'x86_64':
        raise RuntimeError('These binary pins are Linux x86_64 only; use platform-specific upstream packages elsewhere.')
    cache = root / 'downloads'
    cache.mkdir(parents=True, exist_ok=True)
    for item in manifest['downloads']:
        probe, archive = root / item['probe'], cache / item['file']
        if item['kind'] == 'data' and probe.exists() and digest(probe) == item['sha256']:
            continue
        if not archive.exists():
            # Download into a unique file; a failed/interrupted fetch cannot masquerade as an archive.
            with tempfile.NamedTemporaryFile(dir=cache, delete=False, suffix='.partial') as stream:
                pending = Path(stream.name)
                with urllib.request.urlopen(item['url'], timeout=60) as response:
                    shutil.copyfileobj(response, stream)
            if digest(pending) != item['sha256']:
                raise RuntimeError(f'Checksum mismatch; retained untrusted download at {pending}. Do not execute it.')
            pending.rename(archive)
        if digest(archive) != item['sha256']:
            raise RuntimeError(f'Checksum mismatch: {archive}; not executing or replacing it.')
        if probe.exists():
            if item['kind'] == 'data':
                raise RuntimeError(f'Existing OCR data differs: {probe}; inspect before replacing.')
            continue
        target = root / item['target']
        if item['kind'] == 'data':
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(archive, target)
        else:
            if target.exists() and any(target.iterdir()):
                raise RuntimeError(f'Incomplete nonempty installation at {target}; inspect before retrying.')
            target.mkdir(parents=True, exist_ok=True)
            if item['kind'] == 'deb':
                subprocess.run(['dpkg-deb', '-x', str(archive), str(target)], check=True)
            else:
                archive.chmod(0o755)
                subprocess.run([str(archive), '--appimage-extract'], cwd=target, check=True, stdout=subprocess.DEVNULL)
        print('Installed ' + item['name'], flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tools', type=Path, required=True)
    parser.add_argument('--check', action='store_true', help='Offline/read-only inventory and checksum check')
    args = parser.parse_args()
    manifest = json.loads((PACKAGE / 'assets/toolchain.json').read_text())
    root = args.tools.resolve()
    if not args.check:
        install(root, manifest)
    raise SystemExit(0 if check(root, manifest) else 1)


if __name__ == '__main__':
    main()
