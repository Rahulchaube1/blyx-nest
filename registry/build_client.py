"""Cross-compile the standalone CLI for release. No external Go modules are needed."""
import hashlib
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile

ROOT=Path(__file__).resolve().parents[1]
version=sys.argv[1]
if version!='0.1.0':
    raise ValueError('Release tag must match this CLI version')
out=ROOT/'dist'
out.mkdir(exist_ok=True)
sums=[]
with tempfile.TemporaryDirectory() as tmp:
    for platform, arch in [('windows','amd64'),('linux','amd64'),('linux','arm64'),('darwin','arm64'),('darwin','amd64')]:
        name='nest.exe' if platform=='windows' else 'nest'
        exe=Path(tmp)/name
        subprocess.run(['go','build','-trimpath','-ldflags=-s -w -buildid=','-o',str(exe),'./cmd/nest'],cwd=ROOT,
                       env=dict(os.environ,GOOS=platform,GOARCH=arch,CGO_ENABLED='0'),check=True)
        filename=f'nest-{version}-{platform}-{arch}.'+('zip' if platform=='windows' else 'tar.gz')
        archive=out/filename
        if platform=='windows':
            with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as z:
                for src,target in [(exe,name),(ROOT/'LICENSE-MIT','LICENSE-MIT'),(ROOT/'LICENSE-APACHE','LICENSE-APACHE')]:
                    z.write(src,target)
        else:
            with tarfile.open(archive,'w:gz') as z:
                for src,target in [(exe,name),(ROOT/'LICENSE-MIT','LICENSE-MIT'),(ROOT/'LICENSE-APACHE','LICENSE-APACHE')]:
                    z.add(src,arcname=target,recursive=False)
        sums.append(hashlib.sha256(archive.read_bytes()).hexdigest()+'  '+filename)
(out/'SHA256SUMS').write_text('\n'.join(sums)+'\n',encoding='utf-8',newline='\n')
