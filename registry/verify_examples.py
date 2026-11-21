"""Install every archive with Nest and check its exact native program output."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import functools
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import tempfile
from threading import Thread
import urllib.request

ROOT=Path(__file__).resolve().parents[1]


class Quiet(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def verify(base, nest, compiler):
    with urllib.request.urlopen(base+'/api/v1/index.json',timeout=40) as response:
        packages=json.load(response)['packages']
    env=dict(os.environ,BLYX_NEST_URL=base)
    def example(package):
        slug=package['slug']
        with tempfile.TemporaryDirectory(prefix='blyx-example-') as temp:
            subprocess.run([nest,'demo',slug+'@'+package['latest']],cwd=temp,env=env,timeout=100,check=True,stdout=subprocess.DEVNULL)
            project=Path(temp)/(slug+'-demo')
            actual=subprocess.run([compiler,'native-run','main.blyx'],cwd=project,text=True,capture_output=True,timeout=90)
            expected=(project/'expected.txt').read_text('utf-8')
            if actual.returncode or actual.stdout!=expected:
                raise ValueError(f'{slug} failed: {actual.stderr[:500]} {actual.stdout!r} != {expected!r}')
        return slug
    with ThreadPoolExecutor(max_workers=3) as pool:
        for i,slug in enumerate(pool.map(example,packages),1):
            if i%25==0 or i==len(packages):
                print(f'Passed {i}/{len(packages)} Blyx programs',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url')
    parser.add_argument('--nest',type=Path,required=True)
    parser.add_argument('--compiler',type=Path,required=True)
    args=parser.parse_args()
    if args.url:
        verify(args.url.rstrip('/'),args.nest.resolve(),args.compiler.resolve())
    else:
        with ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Quiet,directory=str(ROOT/'public'))) as httpd:
            Thread(target=httpd.serve_forever,daemon=True).start()
            try: verify(f'http://127.0.0.1:{httpd.server_port}',args.nest.resolve(),args.compiler.resolve())
            finally: httpd.shutdown()
