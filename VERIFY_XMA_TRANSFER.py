"""Validate a clone plus this supplement using only the Python standard library."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys


ROOT = Path(__file__).resolve().parent


def safe_path(relative):
    path = (ROOT / relative).resolve()
    if not path.is_relative_to(ROOT):
        raise ValueError(f'Path escapes project: {relative}')
    return path


def sha256(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(chunk)
    return value.hexdigest()


def main():
    manifest = json.loads((ROOT / 'XMA_TRANSFER_MANIFEST.json').read_text(encoding='utf-8'))
    errors = []
    for item in manifest['files']:
        path = safe_path(item['path'])
        if not path.is_file():
            errors.append('Missing package file: ' + item['path'])
        elif path.stat().st_size != item['bytes'] or sha256(path) != item['sha256']:
            errors.append('Changed package file: ' + item['path'])

    required = manifest['required_from_git']
    for item in required:
        if not safe_path(item['path']).is_file():
            errors.append('Missing clone data: ' + item['path'])
    if not (ROOT / '.git').exists():
        errors.append('No project .git: extract into the cloned project root, not a separate folder.')
    else:
        try:
            head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
            ancestry = subprocess.run(['git', 'merge-base', '--is-ancestor', manifest['base_commit'], 'HEAD'], cwd=ROOT, capture_output=True)
            if ancestry.returncode:
                errors.append('HEAD does not contain the published baseline: ' + head)
            present = [item for item in required if safe_path(item['path']).is_file()]
            result = subprocess.run(['git', 'hash-object', '--stdin-paths'], cwd=ROOT,
                input=('\n'.join(item['path'] for item in present) + '\n').encode('utf-8'), capture_output=True)
            if result.returncode:
                errors.append('git hash-object failed: ' + result.stderr.decode('utf-8', errors='replace'))
            else:
                values = result.stdout.decode('ascii').splitlines()
                if len(values) != len(present):
                    errors.append('Unexpected Git object count.')
                for item, value in zip(present, values):
                    if value != item['git_blob_oid']:
                        errors.append('Changed clone data: ' + item['path'])
            print('Git HEAD:', head)
        except (OSError, subprocess.SubprocessError) as exc:
            errors.append('Git verification failed: ' + str(exc))

    if errors:
        print('\n'.join(errors))
        return 1
    print(f"PASS: {len(manifest['files'])} package files and {len(required)} cloned data files verified.")
    print('Historical batch is evidence only. Create a NEW batch after adapting memory limits.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
