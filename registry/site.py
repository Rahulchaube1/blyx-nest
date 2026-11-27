"""Build the public HTML registry, JSON API and downloadable source projects."""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
from html import escape as esc
import json
from pathlib import Path
import shutil
from artwork import BLYX_SITE, read_catalog_artwork, write_icon
from inventory import release_inventory
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
<nav aria-label="Registry"><a href="index.html">Registry</a><a href="stats.html">Statistics</a><a href="install.html">Install</a><a href="publish.html">Publish a package</a></nav>
<a class="upstream" href="{LANG}">Blyx language <span aria-hidden="true">↗</span></a></div></header>
<main class="shell" id="content">{body}</main>
<footer><div class="shell footer"><a class="brand" href="index.html">Blyx Nest</a><a href="api/v1/index.json">Registry API</a><a href="sdk.html">SDK</a>
<a href="ecosystem.html">Developer guide</a><a href="{PROJECT}">Registry source</a><a href="{LANG}/community">Community</a><a href="https://discord.gg/ZPNWqNsvC">Blyx Discord</a><a href="{LANG}/#sponsor">Sponsor Blyx</a></div></footer></body></html>'''


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
<div class="filters" aria-label="Filter by type">'''+filters+'</div><p class="sr" id="status" role="status" aria-live="polite"></p><div class="entries" id="entries">'+''.join(card(p) for p in rows[:18])+'''</div><p id="empty" hidden>No matches. Try a shorter term or choose another type.</p><p id="load-error" role="alert" hidden>Could not load search. <a href="directory.html">Browse the complete directory</a> or <button type="button" id="retry-search">retry</button>.</p><div class="pager"><button type="button" id="previous" disabled>Previous</button><span id="page-number">Page 1 of '''+str((total+17)//18)+'''</span><button type="button" id="next">Next</button></div><p><a href="directory.html">Complete alphabetical directory</a> · <a href="stats.html">Registry statistics</a></p></section>'''
    write('index.html',page('index.html','Blyx Nest · The Blyx package registry','Search and install Blyx frameworks, libraries and developer tools.',content))
    write_json(OUT/'api/v1/discovery.json', [{k:r[k] for k in ('slug','title','kind','latest','description','icon')} for r in rows])
    listing=''.join('<li>'+anchor(('tools/' if r['kind']=='tool' else 'packages/')+r['slug']+'.html', r['title'])+'</li>' for r in sorted(rows,key=lambda r:r['title'].casefold()))
    write('directory.html',page('directory.html','Package directory · Blyx Nest','All published packages and tools.','<h1>Package directory</h1><ul class="alphabetical">'+listing+'</ul>'))


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
        rows+=f'<tr><th scope="row">{v}</th><td>{anchor("files/"+slug+"/"+v+".zip","Download ZIP")} · {anchor("releases/"+slug+"/"+v+".html","Browse files")}</td><td>{anchor(x["repository"]+"/tree/"+x["commit"],x["commit"][:10])}</td><td><code class="digest">{x["sha256"]}</code></td></tr>'
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


def files_page(r, manifest, members, previous):
    slug,v=r['slug'],r['version']
    dest=f'releases/{slug}/{v}.html'
    items=''.join(f'<tr><th scope="row">{anchor(f["url"],f["path"])}</th><td>{f["size"]:,}</td><td><code class="digest">{f["sha256"]}</code></td></tr>' for f in members)
    body=f'''<p class="crumb">{anchor("packages/"+slug+".html",r['title'])} / {v}</p>
<h1>Release files</h1><p class="lede">{esc(r["title"])} {v} contains {len(members):,} files. Open a file to read its published bytes.</p>
<p>{anchor("files/"+slug+"/"+v+".zip","Download ZIP")} ({r["size"]:,} bytes) · {anchor(manifest,"File manifest (JSON)")}</p>
<div class="table"><table><thead><tr><th>File path</th><th>Bytes</th><th>File SHA-256</th></tr></thead><tbody>{items}</tbody></table></div>'''
    if previous:
        prior_version,prior_files=previous
        before={f['path']:f for f in prior_files}
        after={f['path']:f for f in members}
        differences=[('Added',after,sorted(after.keys()-before.keys())),
                     ('Changed',after,sorted(n for n in before.keys() & after.keys() if before[n]['sha256']!=after[n]['sha256'])),
                     ('Removed',before,sorted(before.keys()-after.keys()))]
        body+='<section><h2>Changes since '+esc(prior_version)+'</h2><p>'+anchor(f'releases/{slug}/{prior_version}.html','Browse the previous release')+'</p>'
        if any(names for _,_,names in differences):
            body+='<ul>'+''.join('<li>'+kind+' · '+anchor(source[n]['url'],n)+'</li>' for kind,source,names in differences for n in names)+'</ul>'
        else:
            body+='<p>All file paths and contents match the previous release.</p>'
        body+='</section>'
    write(dest,page(dest,r['title']+' '+v+' files · Blyx Nest','Explore the files in this exact package version.',body))


def statistics(index, tools, counts, file_types):
    stats={'schema':1,'publishedAt':datetime.now(timezone.utc).isoformat(timespec='seconds'),
           'packages':len(index),'frameworks':sum(p['kind']=='framework' for p in index),
           'libraries':sum(p['kind']=='library' for p in index),'tools':len(tools),
           **counts,'fileTypes':dict(file_types.most_common())}
    write_json(OUT/'api/v1/stats.json',stats)
    metrics=[('packages','Packages'),('releases','Package releases'),('members','Files across releases'),('tools','Developer tools')]
    numbers=''.join(f'<div><dt>{label}</dt><dd data-metric="{k}">{stats[k]:,}</dd></div>' for k,label in metrics)
    bars=''.join(f'<li><span>{esc(ext)}</span><meter min="0" max="{max(file_types.values())}" value="{n}">{n}</meter><strong>{n:,}</strong></li>' for ext,n in file_types.most_common()) if file_types else ''
    text=f'''<h1>Registry statistics</h1><p class="lede">Counts from the latest published catalog. A file present in two releases counts twice.</p>
<p id="snapshot" data-published="{stats['publishedAt']}">Published <time>{stats['publishedAt']}</time>. Checks for updates every minute while open. <a href="api/v1/stats.json">Read the data</a></p>
<dl class="metrics">{numbers}</dl><section class="reading"><h2>Files by type</h2><ul class="file-bars">{bars}</ul></section>'''
    timing=json.loads((ROOT/'web/packaging-benchmark.json').read_bytes())
    med=timing['medians']
    bars=''.join(f'<li><span>{label}</span><meter min="0" max="{max(med.values())}" value="{med[k]}"></meter><strong>{med[k]:.2f} s</strong></li>' for k,label in [('before','Before'),('after','After')])
    text+=f'''<section class="reading"><h2>Time to prepare BlyxTorch 0.5.0</h2><p>Median of five Windows x64 runs packaging the same 55-file release. Nest now reads pinned Git blobs in one process. Both versions produced the published archive SHA-256.</p><ul class="file-bars">{bars}</ul><p>{anchor('packaging-benchmark.json','Measurements and method')} · {anchor('releases/blyxtorch/0.5.0.html','Inspect the measured release')}</p></section>'''
    write('stats.html',page('stats.html','Registry statistics · Blyx Nest','Counts and file types for published Blyx releases.',text))


def docs_pages():
    guide='''<article class="guide"><h1>Build and ship a Blyx project</h1><p class="lede">Follow one program from its first run to a release another developer can reproduce.</p>
<h2>Choose an execution target</h2><p>Try a small program in the <a href="https://www.blyx-lang.space/play">browser playground</a>. For local work, choose a compiler for your operating system from <a href="https://www.blyx-lang.space/download">Blyx downloads</a>. The self-hosted compiler covers integer and control-flow programs. Use the documented host toolchain for the native examples on Nest.</p>
<h2>Start with a working example</h2><p>Network reads can split one Unicode character across two buffers. Install <a href="packages/utf8_stream.html">UTF-8 Stream</a> to validate the bytes across both reads. The included example tests the boundary in the three-byte euro sign.</p>'''+code('nest demo utf8_stream@0.1.0\nblyxc native-run utf8_stream-demo/main.blyx')+'''
<h2>Connect to another program</h2><p><a href="packages/netstring_stream.html">Netstring Stream</a> recognizes binary message boundaries, including an empty message or a comma inside the payload. Your application supplies the socket and passes each incoming byte to the parser. For an HTTP integration with Nest itself, the <a href="sdk.html">registry SDK</a> reads a published file by exact version and verifies its digest.</p>
<h2>Plan storage and recovery</h2><p>Use <a href="packages/edition_review.html">Edition Review</a> for review decisions or <a href="packages/outbox_delivery.html">Outbox Delivery</a> to exercise a delivery workflow. Your application must persist state and perform database writes. Test restart and duplicate delivery against your chosen database before deployment.</p>
<h2>Test and distribute</h2><p>Compare your example's complete output with <code>expected.txt</code>. Commit the manifest and license with your source, publish a tagged version, then follow the <a href="publish.html">author guide</a>. Nest CI installs and runs the examples before deploying the catalog. Record a specific package version in your application and commit the generated lock files.</p>
<h2>Observe the deployed software</h2><p>Use your hosting provider's logs and metrics for application errors, latency and usage. The <a href="stats.html">Nest statistics</a> describe published software. For packaging help, ask in the <a href="https://discord.gg/ZPNWqNsvC">Blyx Language Discord</a>.</p></article>'''
    write('ecosystem.html',page('ecosystem.html','Build and ship a Blyx project · Blyx Nest','Learn the execution targets, protocol libraries, SDK, package workflow and deployment checks.',guide))
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
    sdk_doc = """<h1>Nest JavaScript SDK</h1><p class="lede">Read a Blyx source file in a browser or Node.js 20+ without downloading its package archive. The SDK verifies the file's SHA-256 digest.</p>"""
    sdk_doc += anchor('nest-sdk.mjs','Download the standalone ES module','button') + code("import { NestClient } from './nest-sdk.mjs';\nconst client = new NestClient();\nconst release = await client.manifest('moments', '0.1.0');\nconst bytes = await client.readFile(release, 'main.blyx');\nconsole.log(new TextDecoder().decode(bytes));")
    sdk_doc += '<p>For Node projects, <a href="https://github.com/Rahulchaube1/blyx-nest-js/releases/tag/v0.1.0">download the npm-compatible tarball</a> and install it with <code>npm install ./blyx-lang-nest-client-0.1.0.tgz</code>.</p><p>Use <code>await client.catalog()</code> to discover packages. Inspect <code>release.files</code> to list paths, byte lengths and checksums. HTTP, missing-file and checksum errors reject the promise.</p>'
    write('sdk.html',page('sdk.html','JavaScript SDK · Blyx Nest','Read verified Blyx release files from another application.',sdk_doc))
    text='''<div class="crumb"><a href="index.html">Registry</a> / Publish</div><article class="guide"><h1>Publish to Blyx Nest</h1>
<p class="lede">Submit a versioned Blyx library or framework, or propose a tool built specifically for Blyx.</p>
<h2>Prepare your release</h2><p>Commit a Blyx.toml manifest, a public .blyx module and its license to your source repository. Give the release a stable X.Y.Z version. Supply a runnable main.blyx that imports the module from vendor and an expected.txt containing its exact output.</p>
<h2>Submit a package</h2><p>Fork the registry and clone your fork. From that checkout, use Python 3.11 or newer to prepare the archive and release record. Replace the paths, tag, module and project details with your own.</p>'''+code('python registry/submit.py ../my-package --ref v0.1.0 --repository https://github.com/OWNER/REPO --kind library --title MyPackage --description "Describe the task it solves" --module mypackage --license MIT --example ../demo/main.blyx --expected ../demo/expected.txt')+'''
<p>Append <code>--dry-run</code> to the command to validate a release before writing it. Commit the new files under <code>entries/</code> and <code>archives/</code> and open a pull request. Registry checks validate the manifest, module, license, archive paths and checksum. A maintainer verifies the source ownership and example before merging. Merged releases are deployed automatically. Existing versions are immutable.</p>
<h2>List a developer tool</h2><p>For a compiler, package client or another tool specific to Blyx, include its source repository, versioned downloads, license, install guide and a command that demonstrates its Blyx integration.</p><div class="links">'''+anchor(PROJECT+'/fork','Fork registry','button')+anchor(PROJECT+'/compare','Open a pull request')+anchor(PROJECT+'/issues/new?template=tool.yml','Propose a Blyx tool')+'</div></article>'
    write('publish.html',page('publish.html','Publish a package · Blyx Nest','Submit a native Blyx package or a tool for the Blyx ecosystem.',text))


def build(artwork_dir=None):
    artwork = read_catalog_artwork(artwork_dir)
    OUT.mkdir(exist_ok=True)
    for file in ('style.css','nest.js','nest-sdk.mjs','packaging-benchmark.json','blyx.png'):
        shutil.copyfile(ROOT/'web'/file,OUT/file)
    write('.nojekyll','')
    moves = json.loads((ROOT / "registry/approved-project-moves.json").read_bytes())
    groups=defaultdict(list)
    counts={'releases':0,'members':0}
    file_types=Counter()
    originals=set()
    for meta in sorted((ROOT/'entries').glob('*/*.json')):
        rec=json.loads(meta.read_bytes())
        check_metadata(rec)
        slug,v=rec['slug'],rec['version']
        require(meta.parent.name==slug and meta.stem==v, 'Release path does not match metadata')
        archive=ROOT/'archives'/slug/(v+'.zip')
        originals.add(archive)
        groups[slug].append(rec)
    require(originals==set((ROOT/'archives').rglob('*.zip')), 'Archive has no registry entry')
    index=[]
    release_pages=[]
    for slug,versions in sorted(groups.items()):
        rows=sorted(versions,key=lambda r:tuple(map(int,r['version'].split('.'))),reverse=True)
        latest=rows[0]
        previous=None
        for rec in reversed(rows):
            v=rec['version']
            blob=(ROOT/'archives'/slug/(v+'.zip')).read_bytes()
            contents=decode_archive(rec,blob)
            asset='files/'+slug+'/'+v+'.zip'
            dest=OUT/asset
            dest.parent.mkdir(parents=True,exist_ok=True)
            dest.write_bytes(blob)
            manifest,members=release_inventory(OUT,rec,contents)
            rec['fileManifest']=manifest
            files_page(rec,manifest,members,previous)
            previous=(v,members)
            release_pages.append(f'/releases/{slug}/{v}.html')
            counts['releases']+=1
            counts['members']+=len(members)
            file_types.update(Path(f['path']).suffix.lower() or 'No extension' for f in members)
            if rec is latest:
                files=contents
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
    statistics(index,tools,counts,file_types)
    docs_pages()
    locations = ['/', '/install.html', '/publish.html','/directory.html','/stats.html','/sdk.html','/ecosystem.html',*release_pages]
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
