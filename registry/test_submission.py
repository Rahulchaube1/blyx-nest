"""Exercise the author command in a disposable registry and Git project."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from zipfile import ZipFile

SOURCE=Path(__file__).resolve().parent
with tempfile.TemporaryDirectory() as scratch:
    root=Path(scratch)
    tools=root/'registry'; tools.mkdir()
    for name in ('package.py','submit.py'):
        shutil.copyfile(SOURCE/name,tools/name)
    upstream=root/'upstream'
    subprocess.run(['git','init','-q',str(upstream)],check=True)
    (upstream/'Blyx.toml').write_text('[package]\nname="sample"\nversion="0.1.0"\n')
    (upstream/'sample.blyx').write_text('pub fn one() -> i64 { 1 }\n')
    (upstream/'LICENSE').write_text('MIT\n')
    (upstream/'unrelated.js').write_text('// outside the published Blyx package\n')
    subprocess.run(['git','add','.'],cwd=upstream,check=True)
    subprocess.run(['git','-c','user.name=Registry test','-c','user.email=test@localhost','commit','-qm','Sample'],cwd=upstream,check=True)
    (root/'main.blyx').write_text('use vendor::sample::sample;\nfn main() { println!(one()); }\n')
    (root/'expected.txt').write_text('1\n')
    argv=[sys.executable,str(tools/'submit.py'),str(upstream),'--repository','https://github.com/example/sample','--title','Sample',
          '--description','Return one integer.','--kind','library','--module','sample','--license','MIT',
          '--example',str(root/'main.blyx'),'--expected',str(root/'expected.txt')]
    subprocess.run(argv,check=True)
    metadata=json.loads((root/'entries/sample/0.1.0.json').read_bytes())
    archive=root/'archives/sample/0.1.0.zip'
    original=archive.read_bytes()
    with ZipFile(archive) as z:
        assert set(z.namelist())=={'main.blyx','expected.txt','vendor/sample/sample.blyx','vendor/sample/Blyx.toml','vendor/sample/LICENSE'}
    assert metadata['commit']==subprocess.check_output(['git','rev-parse','HEAD'],cwd=upstream,text=True).strip()
    retry=subprocess.run(argv,capture_output=True,text=True)
    assert retry.returncode and 'already exists' in retry.stderr and archive.read_bytes()==original
print('Validated the author workflow and immutable releases.')
