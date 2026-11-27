"""Prepare one new release from the selected commit in a local Git repository."""
import argparse
import io
import subprocess
from pathlib import Path
import tomllib
from package import ROOT, allowed, encode_archive, good_path, publish_files, require


def git(repo, *args):
    return subprocess.check_output(['git','-C',str(repo),*args])


def prepare(args):
    source = args.source.resolve()
    commit = git(source, 'rev-parse', '--verify', args.ref+'^{commit}').decode().strip()
    tracked = git(source, 'ls-tree', '-r', '-z', commit).decode().split('\0')
    source_files = {}
    blobs = []
    subdir = getattr(args, 'source_dir', None)
    if subdir is not None:
        require(good_path(subdir), 'Use a repository-relative package directory')
    selected = subdir+'/' if subdir else ''
    for line in filter(None, tracked):
        details, name = line.split('\t',1)
        if not name.startswith(selected):
            continue
        name = name[len(selected):]
        mode, kind, oid = details.split()
        if mode == '160000':
            raise ValueError('Vendor dependencies as committed Blyx source before submitting')
        if mode.startswith('100') and kind == 'blob' and allowed(name):
            blobs.append((name,oid))
    # Request the pinned Git bytes, including files with export attributes, in one process.
    payload = ''.join(oid+'\n' for _,oid in blobs).encode('ascii')
    stream = io.BytesIO(subprocess.check_output(['git','-C',str(source),'cat-file','--batch'],input=payload))
    for name,oid in blobs:
        obj,kind,size = stream.readline().split()
        require(obj.decode()==oid and kind==b'blob', 'Git returned an unexpected source object')
        body=stream.read(int(size))
        require(len(body)==int(size) and stream.read(1)==b'\n', 'Incomplete Git source object')
        source_files[name]=body
    require('Blyx.toml' in source_files, 'Selected package directory must contain a committed Blyx.toml')
    manifest = tomllib.loads(source_files['Blyx.toml'].decode())['package']
    original = manifest['name']
    slug = original.removeprefix('blyx-')
    record = {'slug':slug, 'version':manifest['version'], 'module':args.module, 'kind':args.kind,
              'repository':args.repository, 'commit':commit, 'title':args.title,
              'description':args.description, 'license':args.license}
    if subdir:
        record['sourceDir'] = subdir
    files = {'vendor/'+slug+'/'+k:v for k,v in source_files.items()}
    files['main.blyx'] = args.example.read_bytes()
    files['expected.txt'] = args.expected.read_bytes()
    require('fn main' in files['main.blyx'].decode(), 'Supply a Blyx example with fn main')
    if getattr(args,'dry_run',False):
        archive=encode_archive(record,files)
        print(f'Validated {slug}@{record["version"]}: {len(files)} files, {len(archive)} archive bytes.')
        return
    publish_files(record,files)
    print('Prepared',slug+'@'+record['version'],'under entries/ and archives/. Open a pull request for review.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=Path)
    parser.add_argument('--ref',default='HEAD')
    parser.add_argument('--dry-run',action='store_true',help='Validate and package the release in memory without writing a registry entry')
    parser.add_argument('--source-dir', help='Git-relative package root within a monorepo')
    for field in ('repository','title','description','module','license'):
        parser.add_argument('--'+field,required=True)
    parser.add_argument('--kind',choices=('library','framework'),required=True)
    parser.add_argument('--example',type=Path,required=True)
    parser.add_argument('--expected',type=Path,required=True)
    prepare(parser.parse_args())
