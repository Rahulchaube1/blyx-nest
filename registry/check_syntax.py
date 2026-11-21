"""Parse each declared Blyx module and entry point without running package code."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

ROOT=Path(__file__).resolve().parents[1]
compiler=Path(sys.argv[1]).resolve()
count=0
with tempfile.TemporaryDirectory() as directory:
    check=Path(directory)/'program.blyx'
    for entry in sorted((ROOT/'entries').glob('*/*.json')):
        record=json.loads(entry.read_bytes())
        slug=record['slug']
        with zipfile.ZipFile(ROOT/'archives'/slug/(record['version']+'.zip')) as archive:
            for name in ('main.blyx','vendor/'+slug+'/'+record['module']+'.blyx'):
                check.write_bytes(archive.read(name))
                result=subprocess.run([compiler,'check',check],capture_output=True)
                if result.returncode:
                    raise ValueError(f'{slug} / {name}: {result.stderr.decode(errors="replace")[:500]}')
                count+=1
print('Parsed',count,'Blyx entry points and public modules')
