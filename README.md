# Blyx Nest

Blyx Nest is the package registry for the Blyx programming language. Browse native Blyx frameworks and libraries by task, look up Blyx developer tools, or install the exact source used by a published example. [Registry](https://nest.blyx-lang.space/) · [Registry on the Blyx website](https://www.blyx-lang.space/nest/index.html) · [Install the client](https://www.blyx-lang.space/nest/install.html)

## Use a package

Download the Nest CLI for your platform and put the executable on your PATH. The client validates the SHA-256 digest before installing a package. In a project created with `blyxc new`, Nest installs into `src/vendor`. In a flat project with `main.blyx`, it uses `vendor`. [Client releases and checksums](https://github.com/Rahulchaube1/blyx-nest/releases)

```sh
nest search regression
nest info moments
nest add moments@0.1.0
nest install
```

Each file in `nest.lock/` pins one dependency to an exact version and digest. Commit this directory to let collaborators restore those releases. Nest preserves existing files and reports conflicting pins. Packages ship their build-time Blyx dependencies inside their own vendor tree.

To try Moments in a new directory, install the Blyx compiler, Rust and a host linker, then run the example. Its output is 3, 12 and 2 on separate lines. [Blyx compiler](https://www.blyx-lang.space/download)

```sh
nest demo moments@0.1.0
blyxc native-run moments-demo/main.blyx
```

## Publish

Package authors submit versioned source releases by pull request. Prepare one from a checkout of this repository with Python 3.11 or newer and Git. The command reads committed source at the selected ref and writes a release record and ZIP. Use an example that imports the package through `vendor::<id>::<module>`. [Submission guide](https://www.blyx-lang.space/nest/publish.html)

```sh
python registry/submit.py ../my-package --ref v0.1.0 --repository https://github.com/OWNER/REPO --kind library --title MyPackage --module mypackage --description "Describe the task it solves" --license MIT --example ../demo/main.blyx --expected ../demo/expected.txt
python registry/site.py
```

If several packages share a repository, pass a directory relative to the Git root, for example `--source-dir packages/fd_masked_attention`. Nest compares the files in that directory with the pinned commit. Each package directory needs its own manifest, module and license.

The module and source manifest must be committed together. For the ID `mypackage`, the manifest name can be `mypackage` or `blyx-mypackage`. Include a license, keep dependencies in the source tree, and submit a new X.Y.Z release for changes. A reviewer checks that the submitter maintains or is authorized by the source project, that the license permits redistribution, and that the example exercises the public module. Tools listed in the registry must demonstrate a direct Blyx integration. [Propose a tool](https://github.com/Rahulchaube1/blyx-nest/issues/new?template=tool.yml)

## Inspect a published version

Open **Browse files** on any package version to view its exact archive paths, byte sizes and SHA-256 digests. The release view compares files against the preceding version. The package JSON exposes each version’s `fileManifest` path. Identical files share a content address across releases. The [registry SDK](https://nest.blyx-lang.space/sdk.html) checks a selected file before returning its bytes.

[Live registry statistics](https://nest.blyx-lang.space/stats.html) count projects, package releases, tools and archive members after each deployment. [Build and ship a Blyx project](https://nest.blyx-lang.space/ecosystem.html) covers runtimes, protocol integrations and the publishing workflow. Ask for help in the [Blyx Language Discord](https://discord.gg/ZPNWqNsvC).

## Build and verify

Nest takes framework and library logos from the official Blyx galleries at build time. It matches each package by ID and source repository, checks the artwork digest and serves a local copy. Community packages can supply their own `assets/logo.png`. For an offline build, save the catalog and logo bundle in one directory and pass it to `python registry/site.py --artwork-dir DIRECTORY`. [Package catalog](https://www.blyx-lang.space/packages.json) · [Logo bundle](https://www.blyx-lang.space/blyx-package-logos.zip)

The native Nest client is written in Go and uses the standard library. The package payloads contain Blyx source, licenses, documentation and data. CI checks the metadata, package digests, Blyx manifests and syntax. On the reviewed main branch it installs and runs the examples with the released Blyx compiler before deploying the HTML registry, searchable index and API to GitHub Pages. [Read the API index](https://www.blyx-lang.space/nest/api/v1/index.json)

```sh
go test ./...
go build -o nest ./cmd/nest
python registry/site.py
python -m http.server 8734 --directory public
```

For a local registry set `BLYX_NEST_URL=http://127.0.0.1:8734`. Run `python registry/verify_examples.py --nest ./nest --compiler /path/to/blyxc` to test a locally built registry. Each release's records live in `entries/<id>/<version>.json` and its archive in `archives/<id>/<version>.zip`. Existing releases stay addressable when a newer version is published.

## Maintainer and support

Rahul Chaube maintains Blyx. [GitHub](https://github.com/Rahulchaube1) · [LinkedIn](https://www.linkedin.com/in/rahulchaube1) · [Blyx community](https://www.blyx-lang.space/community) · [GitHub Sponsors](https://github.com/sponsors/Rahulchaube1) · [Buy Me a Coffee](https://buymeacoffee.com/rahulchaube)
