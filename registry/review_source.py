"""Verify newly proposed vendored files against the stated public Git commit."""
import io
import json
from pathlib import Path
import stat
import subprocess
import sys
import urllib.request
import zipfile

from package import ROOT, MAX_CONTENT, MAX_SIZE, allowed, check_metadata, decode_archive, require

changed = subprocess.check_output(['git','diff','--name-only','--diff-filter=A',sys.argv[1]+'...HEAD','--','entries'],cwd=ROOT,text=True).splitlines()
for filename in changed:
    rec=json.loads((ROOT/filename).read_bytes())
    check_metadata(rec)
    full=rec['repository'].split('github.com/')[1]
    url=f'https://codeload.github.com/{full}/zip/{rec["commit"]}'
    with urllib.request.urlopen(url,timeout=40) as response:
        blob=response.read(MAX_SIZE+1)
    require(len(blob)<=MAX_SIZE,'Upstream source archive exceeds supported size')
    prefix=full.rsplit('/',1)[-1]+'-'+rec['commit']+'/'
    source={}
    with zipfile.ZipFile(io.BytesIO(blob)) as upstream:
        members=upstream.infolist()
        require(len(members)<=4000 and sum(m.file_size for m in members)<=MAX_CONTENT,'Upstream source exceeds supported size')
        for m in members:
            require(m.filename.startswith(prefix),'Unexpected source root')
            name=m.filename[len(prefix):]
            if m.is_dir() or stat.S_ISLNK(m.external_attr>>16) or not allowed(name):
                continue
            source[name]=upstream.read(m)
    slug=rec['slug']
    archive=ROOT/'archives'/slug/(rec['version']+'.zip')
    payload=decode_archive(rec,archive.read_bytes())
    vend='vendor/'+slug+'/'
    shipped={name[len(vend):]:body for name,body in payload.items() if name.startswith(vend)}
    require(source==shipped,'Submitted source does not match the pinned Git commit')
    print('Matched upstream source',slug,rec['commit'])
