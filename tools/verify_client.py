"""Offline file-boundary, integrity and dependency verification. Standard library only."""
import ast
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
IGNORED = {'.git', '__pycache__', 'dist', '.venv'}
PRIVATE = {'app', 'server_core', 'vendor', 'audit', 'ownerdata', 'private-state',
           'backups', 'payment-state', 'user-data', 'deploy'}


def safe_member(value):
    path = PurePosixPath(value)
    if (path.is_absolute() or path.as_posix() != value or
            any(part in ('', '.', '..') or ':' in part or '\\' in part for part in path.parts)):
        raise ValueError('Unsafe manifest path: ' + value)
    return path


def verify(root=ROOT):
    root = Path(root).resolve()
    manifest = json.loads((root / 'client-manifest.json').read_text(encoding='utf-8'))
    members = manifest['members']
    skill = manifest['skill_root']
    safe_member(skill)
    expected = set(members) | {'client-manifest.json'}
    local_modules = {Path(name).stem for name in members if name.endswith('.py')}
    actual = set()
    for path in root.rglob('*'):
        relative = path.relative_to(root)
        if path.is_symlink():
            raise ValueError('Symlink rejected: ' + relative.as_posix())
        if any(part in IGNORED for part in relative.parts):
            continue
        if path.is_file():
            actual.add(relative.as_posix())
    if actual != expected:
        raise ValueError('Unlisted or missing files: ' + ', '.join(sorted(actual ^ expected)))
    for name, expected_hash in members.items():
        relative = safe_member(name)
        if any(part in PRIVATE for part in relative.parts):
            raise ValueError('Private tree rejected: ' + name)
        path = root.joinpath(*relative.parts)
        if path.suffix.lower() in {'.pem', '.key', '.p12', '.pfx', '.db', '.zip', '.tgz'} or '.sqlite' in path.name:
            raise ValueError('Private/binary artifact rejected: ' + name)
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != expected_hash:
            raise ValueError('Hash mismatch: ' + name)
        text = data.decode('utf-8')
        if re.search(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----', text):
            raise ValueError('Private key rejected: ' + name)
        if path.suffix == '.py':
            tree = ast.parse(text, filename=name)
            for node in ast.walk(tree):
                imports = ([node.module] if isinstance(node, ast.ImportFrom) else
                           [alias.name for alias in node.names] if isinstance(node, ast.Import) else [])
                if any(module and module.split('.')[0] in PRIVATE for module in imports):
                    raise ValueError('Private import rejected: ' + name)
                if any(module and module.split('.')[0] not in sys.stdlib_module_names | local_modules for module in imports):
                    raise ValueError('Unbundled dependency rejected: ' + name)
        if path.suffix == '.md':
            if 'LicenseRef-All-Rights-Reserved' in text or 'LicenseRef-Ziyou-Basic-Free' in text:
                raise ValueError('Old client license rejected: ' + name)
            for target in re.findall(r'\[[^\]\n]*\]\(([^\s)]+)\)', text):
                parsed = urlsplit(target)
                if parsed.scheme or target.startswith('#'):
                    continue
                destination = (path.parent / unquote(parsed.path)).resolve()
                if not destination.is_relative_to(root) or not destination.exists():
                    raise ValueError('Broken/escaped document link: ' + name + ' -> ' + target)
    entrypoints = sorted(name for name in members if name.endswith('/SKILL.md'))
    if entrypoints != [skill + '/SKILL.md']:
        raise ValueError('Exactly one discoverable Skill is required')
    entry = (root / entrypoints[0]).read_text(encoding='utf-8')
    if not entry.startswith('---\nname: ' + Path(skill).name + '\n') or '\nlicense: MIT\n' not in entry:
        raise ValueError('Invalid Skill name/license')
    for name, original_hash in manifest['preserved_runtime'].items():
        if members.get(name) != original_hash:
            raise ValueError('Preserved runtime differs: ' + name)
    for relative in ('LICENSE', skill + '/LICENSE.md', skill + '/basic/LICENSE.md'):
        if (root / relative).read_bytes() != (root / 'LICENSE').read_bytes():
            raise ValueError('Inconsistent license: ' + relative)
    return {'status': 'passed', 'files': len(expected),
            'preserved_runtime_files': len(manifest['preserved_runtime']),
            'discoverable_skills': len(entrypoints), 'network_calls': 0, 'payment_calls': 0,
            'scope': 'Local integrity/dependency boundary only; not native-host or payment acceptance'}


if __name__ == '__main__':
    try:
        print(json.dumps(verify(), ensure_ascii=False, indent=2))
    except (ValueError, OSError, KeyError, SyntaxError) as error:
        sys.exit(str(error))
