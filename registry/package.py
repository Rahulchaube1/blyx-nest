"""Build portable Blyx archives and validate the registry's release records."""
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import stat
import tomllib
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SLUG = re.compile(r'[a-z][a-z0-9_]{0,47}\Z')
VERSION = re.compile(r'(0|[1-9][0-9]{0,8})\.(0|[1-9][0-9]{0,8})\.(0|[1-9][0-9]{0,8})\Z')
RESERVED = {'con', 'prn', 'aux', 'nul', *(f'{prefix}{i}' for prefix in ('com','lpt') for i in range(1,10))}
MAX_SIZE = 16 * 1024 * 1024
MAX_CONTENT = 48 * 1024 * 1024
SUFFIXES = {'.blyx', '.toml', '.txt', '.md', '.csv', '.json', '.png', '.bt'}
TOOL_IDS = {'blyxc', 'nest'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def write_json(file, value):
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8', newline='\n')


def good_path(name):
    parts = name.split('/')
    return all(re.fullmatch(r'[A-Za-z0-9_-][A-Za-z0-9_. -]{0,119}', p)
               and not p.endswith((' ', '.')) and p.partition('.')[0].lower() not in RESERVED for p in parts)


def check_id(slug):
    require(isinstance(slug, str) and SLUG.fullmatch(slug) and slug not in RESERVED | TOOL_IDS, 'Invalid or reserved package ID')


def allowed(name):
    p = PurePosixPath(name)
    return good_path(name) and (p.suffix.lower() in SUFFIXES or re.fullmatch(r'LICENSE(?:[-.][A-Za-z0-9-]+)?', p.name))


def check_metadata(record):
    slug = record['slug']
    check_id(slug)
    require(VERSION.fullmatch(record['version']), 'Expected X.Y.Z version')
    require(SLUG.fullmatch(record['module']) and record['module'] not in RESERVED, 'Invalid Blyx module')
    require(record['kind'] in ('framework', 'library'), 'Expected a Blyx framework or library')
    for key, limit in [('title', 80), ('description', 500), ('license', 100)]:
        value = record[key]
        require(isinstance(value, str) and value.strip() == value and 0 < len(value) <= limit
                and not any(ord(ch) < 32 for ch in value), f'Invalid {key}')
    require(re.fullmatch(r'https://github\.com/[A-Za-z0-9-]+/[A-Za-z0-9_.-]+', record['repository'])
            and record['repository'].rsplit('/',1)[1] not in ('.','..'), 'Expected a GitHub source repository')
    require(re.fullmatch(r'[0-9a-f]{40}', record['commit']), 'Expected a pinned Git commit')


def check_files(record, files):
    slug = record['slug']
    vendor = 'vendor/' + slug + '/'
    require(0 < len(files) <= 1200 and sum(map(len, files.values())) <= MAX_CONTENT, 'Archive exceeds project limits')
    require(len({name.casefold() for name in files}) == len(files), 'Duplicate or case-colliding paths')
    for name in files:
        require(good_path(name) and (name in ('main.blyx','expected.txt') or name.startswith(vendor) and allowed(name)), 'Invalid archive member ' + name)
        parent = PurePosixPath(name).parent
        while parent.parts:
            require(str(parent).casefold() not in {f.casefold() for f in files}, 'File used as a directory')
            parent = parent.parent
    manifest = tomllib.loads(files[vendor+'Blyx.toml'].decode())['package']
    require(manifest.get('name') in (slug, 'blyx-'+slug) and manifest.get('version') == record['version'], 'Blyx.toml name or version mismatch')
    module = files[vendor+record['module']+'.blyx'].decode()
    require(module.strip(), 'Empty Blyx module')
    require('fn main' in files['main.blyx'].decode() and len(files['main.blyx']) < 128*1024, 'Expected a runnable Blyx entry point')
    files['expected.txt'].decode()
    require(any(PurePosixPath(f).parent == PurePosixPath(vendor) and PurePosixPath(f).name.startswith('LICENSE') for f in files), 'Source license missing')


def encode_archive(record, files):
    check_metadata(record)
    check_files(record, files)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as out:
        for name, data in sorted(files.items()):
            member = zipfile.ZipInfo(name, (1980,1,1,0,0,0))
            member.create_system = 3
            member.external_attr = 0o100644 << 16
            out.writestr(member, data, compress_type=zipfile.ZIP_DEFLATED)
    blob = buffer.getvalue()
    require(len(blob) <= MAX_SIZE, 'Compressed package too large')
    return blob


def decode_archive(record, blob):
    require(len(blob) == record['size'] <= MAX_SIZE and hashlib.sha256(blob).hexdigest() == record['sha256'], 'Archive digest or size mismatch')
    contents = {}
    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        entries = archive.infolist()
        require(len(entries) <= 1200 and sum(e.file_size for e in entries) <= MAX_CONTENT, 'Expanded project too large')
        for e in entries:
            require(e.filename not in contents and stat.S_ISREG(e.external_attr >> 16) and good_path(e.filename), 'Unexpected ZIP entry')
            contents[e.filename] = archive.read(e)
    check_files(record, contents)
    return contents


def publish_files(record, files, root=ROOT):
    blob = encode_archive(record, files)
    slug, version = record['slug'], record['version']
    metadata = root/'entries'/slug/(version+'.json')
    archive = root/'archives'/slug/(version+'.zip')
    require(not metadata.exists() and not archive.exists(), 'This package version already exists')
    archive.parent.mkdir(parents=True, exist_ok=True)
    archive.write_bytes(blob)
    write_json(metadata, {**record, 'sha256': hashlib.sha256(blob).hexdigest(), 'size': len(blob)})
