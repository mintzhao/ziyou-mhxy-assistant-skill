"""Build the installable Skill ZIP from verified explicit members, without network."""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile
import zipfile

from verify_client import ROOT, verify


def build(output, root=ROOT):
    root = Path(root).resolve()
    output = Path(output).absolute()
    if output.exists() or output.is_symlink():
        raise ValueError('Output must be a new directory; existing files are never overwritten')
    result = verify(root)
    manifest = json.loads((root / 'client-manifest.json').read_text(encoding='utf-8'))
    skill = manifest['skill_root']
    prefix = skill + '/'
    names = sorted(name for name in manifest['members'] if name.startswith(prefix))
    output.parent.mkdir(parents=True, exist_ok=True)
    filename = Path(skill).name + '-' + manifest['version'] + '.zip'
    with tempfile.TemporaryDirectory(prefix='.skill-build-', dir=output.parent) as temp:
        staging = Path(temp) / 'ready'
        staging.mkdir()
        archive_path = staging / filename
        # Fixed ZIP_STORED bytes are reproducible across zlib/runtime versions.
        with zipfile.ZipFile(archive_path, 'x', compression=zipfile.ZIP_STORED) as archive:
            for name in names:
                member = Path(skill).name + '/' + name[len(prefix):]
                info = zipfile.ZipInfo(member, date_time=(2026, 10, 10, 0, 0, 0))
                info.create_system = 3
                info.external_attr = 0o100644 << 16
                data = (root / name).read_bytes()
                if hashlib.sha256(data).hexdigest() != manifest['members'][name]:
                    raise ValueError('Input changed during build: ' + name)
                archive.writestr(info, data)
        with zipfile.ZipFile(archive_path) as archive:
            if archive.testzip() is not None or len(archive.namelist()) != len(names):
                raise ValueError('Invalid archive')
            for name in names:
                member = Path(skill).name + '/' + name[len(prefix):]
                if hashlib.sha256(archive.read(member)).hexdigest() != manifest['members'][name]:
                    raise ValueError('Invalid archive member')
        sha = hashlib.sha256(archive_path.read_bytes()).hexdigest()
        (staging / 'SHA256SUMS').write_text(sha + '  ' + filename + '\n', encoding='utf-8')
        report = dict(result, filename=filename, sha256=sha, skill_files=len(names), publication='local-only')
        (staging / 'build-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        staging.rename(output)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(build(args.output), ensure_ascii=False, indent=2))
    except (ValueError, OSError, KeyError) as error:
        parser.exit(1, str(error) + '\n')
