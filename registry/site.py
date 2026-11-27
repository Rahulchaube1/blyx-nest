"""Build the public HTML registry, JSON API and downloadable source projects."""
import argparse
from collections import defaultdict
from html import escape as esc
import json
from pathlib import Path
import shutil
from artwork import BLYX_SITE, read_catalog_artwork, write_icon
from package import ROOT, SLUG, check_metadata, decode_archive, require, write_json

PRIMARY = 'https://nest.blyx-lang.space'
PROJECT = 'https://github.com/Rahulchaube1/blyx-nest'
LANG = BLYX_SITE
OUT = ROOT/'public'
CLI_RELEASE = PROJECT+'/releases/tag/v0.1.0'
LICENSES = ('MIT','Apache-2.0')


def write(name, body):
    dest=OUT/name
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(body,encoding='utf-8',newline='\n')


def anchor(url, label, style=''):
    return f'<a class="{style}" href="{esc(url,quote=True)}">{esc(label)}</a>'


def page(location,title,summary,body):
    prefix='../'*(len(Path(location).parts)-1) or './'
    canonical=PRIMARY+('/' if location=='index.html' else '/'+location)
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title><meta name="description" content="{esc(summary,quote=True)}"><link rel="canonical" href="{canonical}">
<base href="{prefix}"><link rel="icon" href="blyx.png"><link rel="stylesheet" href="style.css"><script defer src="nest.js"></script></head>
<body><a class="skip" href="{esc(location)}#content">Skip to content</a><header><div class="shell top">
<a class="brand" href="index.html"><img src="blyx.png" width="38" height="38" alt="">Blyx Nest</a>
<nav aria-label="Registry"><a href="index.html">Registry</a><a href="install.html">Install</a><a href="publish.html">Publish a package</a></nav>
<a class="upstream" href="{LANG}">Blyx language <span aria-hidden="true">↗</span></a></div></header>
<main class="shell" id="content">{body}</main>
<footer><div class="shell footer"><a class="brand" href="index.html">Blyx Nest</a><a href="api/v1/index.json">Registry API</a>
<a href="{PROJECT}">Registry source</a><a href="{LANG}/community">Community</a><a href="{LANG}/#sponsor">Sponsor Blyx</a></div></footer></body></html>'''


def card(p):
    group=p['kind']
    folder='tools' if group=='tool' else 'packages'
    link=folder+'/'+p['slug']+'.html'
    search=' '.join(p[k] for k in ('slug','title','kind','description')).casefold()
    return f'''<article class="entry" data-kind="{group}" data-search="{esc(search,quote=True)}">
<a href="{link}"><img loading="lazy" width="50" height="50" src="{p['icon']}" alt=""><div class="entry-main">
<div class="entry-meta">{esc(group.title())}<span>v{esc(p['latest'])}</span></div><h3>{esc(p['title'])}</h3>
<p>{esc(p['description'])}</p></div></a></article>'''


def code(text):
    return '<pre><code>'+esc(text)+'</code></pre>'


def copy_command(cmd):
    return '<div class="cmd"><code>'+esc(cmd)+'</code><button type="button" data-copy="'+esc(cmd,quote=True)+'" aria-label="Copy command" hidden>Copy</button></div>'


def index_page(packages,tools):
    all_items=packages+tools
    total=len(all_items)
    featured=('blyxtorch','moments','nest','modelgate','retrieval','blyxc')
    hits={slug:i for i,slug in enumerate(featured)}
    rows=sorted(all_items,key=lambda p:(hits.get(p['slug'],len(hits)),p['title'].casefold()))
    filters=''
    for name,slug in [('All','all'),('Frameworks','framework'),('Libraries','library'),('Tools','tool')]:
        count=total if slug=='all' else sum(1 for p in rows if p['kind']==slug)
        filters+=f'<a class="filter" data-filter="{slug}" href="index.html?kind={slug}" aria-current="{"true" if slug=="all" else "false"}">{name} <span>{count}</span></a>'
    content='''<div class="hero"><div><h1>Packages for Blyx<span>.</span></h1><p>Find a framework, import a library, or get a tool for your next Blyx project.</p></div>
<div class="try"><div class="try-title"><img src="blyx.png" width="28" height="28" alt=""> Try a library</div>'''+copy_command('nest add moments@0.1.0')+'''<a href="install.html">Install the Nest CLI <span aria-hidden="true">→</span></a></div></div>
<section aria-labelledby="browse"><div class="search-top"><h2 id="browse">Browse the registry</h2>
<form role="search" action="index.html"><label class="sr" for="query">Search packages and tools</label><input id="query" type="search" name="q" placeholder="Search by name or task" autocomplete="off"></form></div>
<div class="filters" aria-label="Filter by type">'''+filters+'</div><p class="sr" id="status" role="status" aria-live="polite"></p><div class="entries" id="entries">'+''.join(card(p) for p in rows)+'''</div><p id="empty" hidden>No matches. Try a shorter term or choose another type.</p><div class="pager" hidden><button type="button" id="previous">Previous</button><span id="page-number"></span><button type="button" id="next">Next</button></div></section>'''
    write('index.html',page('index.html','Blyx Nest · The Blyx package registry','Search and install Blyx frameworks, libraries and developer tools.',content))


def package_page(data,records):
    slug=data['slug']
    r=records[0]
    title=esc(r['title'])
    version=r['version']
    owner=r['repository'].split('/')[-2]
    loc='packages/'+slug+'.html'
    rows=''
    for x in records:
        v=x['version']
        rows+=f'<tr><th scope="row">{v}</th><td>{anchor("files/"+slug+"/"+v+".zip","Download ZIP")}</td><td>{anchor(x["repository"]+"/tree/"+x["commit"],x["commit"][:10])}</td><td><code class="digest">{x["sha256"]}</code></td></tr>'
    content=f'''<div class="crumb">{anchor("index.html","Registry")} / {esc(r['kind'].title())}</div>
<div class="detail"><div class="detail-lead"><img class="mark" src="{data['icon']}" alt=""><div class="kicker">{esc(r['kind'])} · v{version}</div>
<h1>{title}</h1><p class="lede">{esc(r['description'])}</p><p>{anchor(r['repository'],"Source repository")} · {anchor("api/v1/packages/"+slug+".json","Package JSON")}</p></div>
<aside><h2>Add to a project</h2>{copy_command("nest add "+slug+"@"+version)}<p>{anchor("install.html","Get the Nest CLI")}</p>
<dl><dt>Source owner</dt><dd>{esc(owner)}</dd><dt>License</dt><dd>{esc(r["license"])}</dd><dt>Module</dt><dd><code>{esc(r["module"])}.blyx</code></dd></dl></aside></div>
<section class="reading"><h2>Use {title}</h2>{code("use vendor::"+slug+"::"+r['module']+";")}
<h3>Run the example</h3>{code("nest demo "+slug+"@"+version+chr(10)+"blyxc native-run "+slug+"-demo/main.blyx")}
<details><summary>Example source and expected output</summary>{code(data["program"])}<h3>Expected output</h3>{code(data['output'])}</details></section>
<section><h2>Published versions</h2><div class="table"><table><thead><tr><th>Version</th><th>Package</th><th>Source commit</th><th>SHA-256</th></tr></thead><tbody>{rows}</tbody></table></div></section>'''
    write(loc,page(loc,r['title']+' · Blyx Nest',r['description'],content))


def docs_pages():
    files=['windows-amd64.zip','linux-amd64.tar.gz','linux-arm64.tar.gz','darwin-arm64.tar.gz','darwin-amd64.tar.gz']
    labels=['Windows x64','Linux x64','Linux ARM64','macOS Apple silicon','macOS Intel']
    downloads=''.join('<li>'+anchor(PROJECT+'/releases/download/v0.1.0/nest-0.1.0-'+file,label)+'</li>' for file,label in zip(files,labels))
    text='''<div class="crumb"><a href="index.html">Registry</a> / Install</div><article class="guide"><h1>Install Nest</h1>
<p class="lede">Download the standalone client for your operating system. Extract the archive and put the executable in a directory on your PATH.</p><ul>'''+downloads+'</ul>'+anchor(PROJECT+'/releases/download/v0.1.0/SHA256SUMS','Release checksums')+'''
<h2>Find a package</h2>'''+code('nest --version\nnest search regression\nnest info moments')+'''
<h2>Add it to a Blyx project</h2><p>Run Nest in the project root. It writes the package under the entry file’s vendor directory and records the exact version and SHA-256 in nest.lock/. Commit that lock directory. A fresh checkout can restore the same dependencies with nest install.</p>'''+code('nest add moments@0.1.0\nnest install')+'''
<p>Import the module from your Blyx entry file.</p>'''+code('use vendor::moments::moments;')+'''
<h2>Run a complete example</h2><p>Install the <a href="https://www.blyx-lang.space/download">Blyx compiler</a>, Rust and a host linker to run native examples. The following creates a new directory and prints 3, 12 and 2 on separate lines.</p>'''+code('nest demo moments@0.1.0\nblyxc native-run moments-demo/main.blyx')+'''
<h2>Use the API</h2><p>The <a href="api/v1/index.json">registry index</a> lists all packages and tools. Each <a href="api/v1/packages/moments.json">package record</a> includes its versions, source commits and SHA-256 digests. Archive paths are relative to the registry root.</p></article>'''
    write('install.html',page('install.html','Install Nest · Blyx Nest','Download the Nest CLI and install pinned Blyx source packages.',text))
    text='''<div class="crumb"><a href="index.html">Registry</a> / Publish</div><article class="guide"><h1>Publish to Blyx Nest</h1>
<p class="lede">Submit a versioned Blyx library or framework, or propose a tool built specifically for Blyx.</p>
<h2>Prepare your release</h2><p>Commit a Blyx.toml manifest, a public .blyx module and its license to your source repository. Give the release a stable X.Y.Z version. Supply a runnable main.blyx that imports the module from vendor and an expected.txt containing its exact output.</p>
<h2>Submit a package</h2><p>Fork the registry and clone your fork. From that checkout, use Python 3.11 or newer to prepare the archive and release record. Replace the paths, tag, module and project details with your own.</p>'''+code('python registry/submit.py ../my-package --ref v0.1.0 --repository https://github.com/OWNER/REPO --kind library --title MyPackage --description "Describe the task it solves" --module mypackage --license MIT --example ../demo/main.blyx --expected ../demo/expected.txt')+'''
<p>Commit the new files under <code>entries/</code> and <code>archives/</code> and open a pull request. Registry checks validate the manifest, module, license, archive paths and checksum. A maintainer verifies the source ownership and example before merging. Merged releases are deployed automatically. Existing versions are immutable.</p>
<h2>List a developer tool</h2><p>For a compiler, package client or another tool specific to Blyx, include its source repository, versioned downloads, license, install guide and a command that demonstrates its Blyx integration.</p><div class="links">'''+anchor(PROJECT+'/fork','Fork registry','button')+anchor(PROJECT+'/compare','Open a pull request')+anchor(PROJECT+'/issues/new?template=tool.yml','Propose a Blyx tool')+'</div></article>'
    write('publish.html',page('publish.html','Publish a package · Blyx Nest','Submit a native Blyx package or a tool for the Blyx ecosystem.',text))


def build(artwork_dir=None):
    artwork = read_catalog_artwork(artwork_dir)
    OUT.mkdir(exist_ok=True)
    for file in ('style.css','nest.js','blyx.png'):
        shutil.copyfile(ROOT/'web'/file,OUT/file)
    write('.nojekyll','')
    moves = json.loads((ROOT / "registry/approved-project-moves.json").read_bytes())
    groups=defaultdict(list)
    originals=set()
    for meta in sorted((ROOT/'entries').glob('*/*.json')):
        rec=json.loads(meta.read_bytes())
        check_metadata(rec)
        slug,v=rec['slug'],rec['version']
        require(meta.parent.name==slug and meta.stem==v, 'Release path does not match metadata')
        archive=ROOT/'archives'/slug/(v+'.zip')
        originals.add(archive)
        blob=archive.read_bytes()
        contents=decode_archive(rec,blob)
        asset='files/'+slug+'/'+v+'.zip'
        dest=OUT/asset
        dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_bytes(blob)
        groups[slug].append((rec,contents))
    require(originals==set((ROOT/'archives').rglob('*.zip')), 'Archive has no registry entry')
    index=[]
    for slug,versions in sorted(groups.items()):
        versions.sort(key=lambda row:tuple(map(int,row[0]['version'].split('.'))),reverse=True)
        rows=[row for row,_ in versions]
        latest,files=versions[0]
        # Retain original source links for immutable releases moved to dedicated repositories.
        for newer, older in zip(rows, rows[1:]):
            if newer['repository'].casefold() == older['repository'].casefold():
                continue
            move = [older['version'], older['commit'], older['repository'], newer['version'], newer['commit'], newer['repository']]
            require(move in moves.get(slug, []), 'A source repository change needs a reviewed migration')
        light={k:latest[k] for k in ('slug','title','kind','description','module')}
        light.update(latest=latest['version'], icon=write_icon(latest, files, artwork, OUT))
        index.append(light)
        data={**light, 'versions':[{**r,'archive':'files/'+slug+'/'+r['version']+'.zip'} for r in rows]}
        write_json(OUT/'api/v1/packages'/(slug+'.json'),data)
        package_page({**data,'program':files['main.blyx'].decode(),'output':files['expected.txt'].decode()},rows)
    tools=[]
    for t in json.loads((ROOT/'registry/tools.json').read_bytes()):
        require(SLUG.fullmatch(t['slug']) and t['slug'] not in groups, 'Invalid tool ID')
        light={k:t[k] for k in ('slug','title','description')}
        light.update(kind='tool',icon='blyx.png',latest=t['version'])
        tools.append(light)
        write_json(OUT/'api/v1/tools'/(t['slug']+'.json'),{**light,**t})
        loc='tools/'+t['slug']+'.html'
        content='<div class="crumb">'+anchor('index.html','Registry')+' / Developer tool</div><article class="guide"><div class="kicker">Blyx tool · v'+esc(t['version'])+'</div><h1>'+esc(t['title'])+'</h1><p class="lede">'+esc(t['description'])+'</p><div class="links">'+anchor(t['guide'],'Install '+t['title'],'button')+anchor(t['release'],'Versioned downloads')+anchor(t['repository'],'Source repository')+'</div></article>'
        write(loc,page(loc,t['title']+' · Blyx Nest',t['description'],content))
    write_json(OUT/'api/v1/index.json',{'schema':1,'packages':index,'tools':tools})
    index_page(index,tools)
    docs_pages()
    locations = ['/', '/install.html', '/publish.html']
    locations.extend('/packages/'+p['slug']+'.html' for p in index)
    locations.extend('/tools/'+t['slug']+'.html' for t in tools)
    write('sitemap.xml', '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'+''.join('<url><loc>'+PRIMARY+loc+'</loc></url>' for loc in locations)+'</urlset>\n')
    write('robots.txt','User-agent: *\nAllow: /\nSitemap: '+PRIMARY+'/sitemap.xml\n')
    print('Built',len(index),'Blyx packages and',len(tools),'developer tools')


if __name__=='__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--artwork-dir', type=Path,
                        help='Read packages.json and blyx-package-logos.zip from a local copy of the Blyx website')
    build(parser.parse_args().artwork_dir)
