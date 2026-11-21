"""Use the Blyx website's package artwork independently of source release versions."""
from hashlib import sha256
from io import BytesIO
import json
from urllib.request import urlopen
from zipfile import ZipFile

from package import SLUG, require


BLYX_SITE = 'https://www.blyx-lang.space'
PNG = b'\x89PNG\r\n\x1a\n'


def read_catalog_artwork(directory=None):
    def read(filename):
        if directory is not None:
            return (directory / filename).read_bytes()
        with urlopen(f'{BLYX_SITE}/{filename}', timeout=45) as response:
            return response.read()

    packages = json.loads(read('packages.json'))['packages']
    require(packages, 'The Blyx package catalog is empty')
    artwork = {}
    with ZipFile(BytesIO(read('blyx-package-logos.zip'))) as bundle:
        for package in packages:
            slug = package['documentation'].rsplit('/', 1)[-1]
            require(SLUG.fullmatch(slug), 'Invalid package ID in the Blyx artwork catalog')
            image = bundle.read(slug + '.png')
            digest = sha256(image).hexdigest()[:12]
            require(image.startswith(PNG) and package['logo'] == f'{BLYX_SITE}/packages/{slug}.png?v={digest}',
                    f'The Blyx gallery and logo bundle disagree for {slug}')
            key = (slug, package['repository'].casefold())
            require(key not in artwork, f'Duplicate artwork for {slug}')
            artwork[key] = image
    return artwork


def write_icon(record, files, artwork, output):
    slug = record['slug']
    image = artwork.get((slug, record['repository'].casefold()))
    if image is None:
        prefix = f'vendor/{slug}/'
        for path, data in files.items():
            if (path.startswith(prefix) and path.endswith('/logo.png')
                    and 'vendor' not in path[len(prefix):].split('/')[:-1] and data.startswith(PNG)):
                image = data
                break
    if image is None:
        return 'blyx.png'

    relative = f'images/{slug}.png'
    path = output / relative
    path.parent.mkdir(exist_ok=True)
    path.write_bytes(image)
    return f'{relative}?v={sha256(image).hexdigest()[:12]}'
