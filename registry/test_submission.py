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
    subprocess.run(argv+['--dry-run'],check=True)
    assert not (root/'entries/sample').exists() and not (root/'archives/sample').exists()
    subprocess.run(argv,check=True)
    metadata=json.loads((root/'entries/sample/0.1.0.json').read_bytes())
    archive=root/'archives/sample/0.1.0.zip'
    original=archive.read_bytes()
    with ZipFile(archive) as z:
        assert set(z.namelist())=={'main.blyx','expected.txt','vendor/sample/sample.blyx','vendor/sample/Blyx.toml','vendor/sample/LICENSE'}
    assert metadata['commit']==subprocess.check_output(['git','rev-parse','HEAD'],cwd=upstream,text=True).strip()
    retry=subprocess.run(argv,capture_output=True,text=True)
    assert retry.returncode and 'already exists' in retry.stderr and archive.read_bytes()==original
    nested = upstream/'packages'/'nested'
    nested.mkdir(parents=True)
    (nested/'Blyx.toml').write_text('[package]\nname="nested"\nversion="0.1.0"\n')
    (nested/'nested.blyx').write_text('pub fn one() -> i64 { 1 }\n')
    (nested/'LICENSE').write_text('MIT\n')
    subprocess.run(['git','add','packages'],cwd=upstream,check=True)
    subprocess.run(['git','-c','user.name=Registry test','-c','user.email=test@localhost','commit','-qm','Nested sample'],cwd=upstream,check=True)
    (root/'main.blyx').write_text('use vendor::nested::nested;\nfn main() { println!(one()); }\n')
    nested_args=list(argv)
    nested_args[nested_args.index('--module')+1]='nested'
    subprocess.run(nested_args+['--source-dir','packages/nested'],check=True)
    assert json.loads((root/'entries/nested/0.1.0.json').read_bytes())['sourceDir']=='packages/nested'
    with ZipFile(root/'archives/nested/0.1.0.zip') as z:
        assert set(z.namelist())=={'main.blyx','expected.txt','vendor/nested/nested.blyx','vendor/nested/Blyx.toml','vendor/nested/LICENSE'}
    for directory, diagnostic in [('packages/missing','committed Blyx.toml'),('../nested','repository-relative')]:
        failure=subprocess.run(nested_args+['--source-dir',directory],capture_output=True,text=True)
        assert failure.returncode and diagnostic in failure.stderr
print('Validated root and nested packages, directory selection and immutable releases.')
