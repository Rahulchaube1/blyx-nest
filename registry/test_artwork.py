"""Check official gallery branding, cache refreshes and community package icons."""
from base64 import b64decode
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, main
from zipfile import ZipFile

from artwork import BLYX_SITE, read_catalog_artwork, write_icon
from package import ROOT


class ArtworkTest(TestCase):
    def test_gallery_overrides_archived_artwork(self):
        official = (ROOT / 'web/blyx.png').read_bytes()
        archived = b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jvGkAAAAASUVORK5CYII=')
        digest = sha256(official).hexdigest()[:12]
        record = {'slug': 'sample', 'repository': 'https://github.com/owner/sample'}
        catalog = {'repository': record['repository'].upper(), 'documentation': BLYX_SITE + '/packages/sample',
                   'logo': f'{BLYX_SITE}/packages/sample.png?v={digest}'}
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'packages.json').write_text(json.dumps({'packages': [catalog]}))
            with ZipFile(root / 'blyx-package-logos.zip', 'w') as bundle:
                bundle.writestr('sample.png', official)
            artwork = read_catalog_artwork(root)
            files = {'vendor/sample/vendor/dependency/assets/logo.png': official,
                     'vendor/sample/assets/logo.png': archived}
            self.assertEqual(write_icon(record, files, artwork, root), f'images/sample.png?v={digest}')
            image_path = root / 'images/sample.png'
            self.assertEqual(image_path.read_bytes(), official)

            community = {**record, 'repository': 'https://github.com/contributor/sample'}
            archive_digest = sha256(archived).hexdigest()[:12]
            self.assertEqual(write_icon(community, files, artwork, root), f'images/sample.png?v={archive_digest}')
            self.assertEqual(image_path.read_bytes(), archived)
            del files['vendor/sample/assets/logo.png']
            self.assertEqual(write_icon(community, files, artwork, root), 'blyx.png')

            with ZipFile(root / 'blyx-package-logos.zip', 'w') as bundle:
                bundle.writestr('sample.png', archived)
            with self.assertRaisesRegex(ValueError, 'disagree for sample'):
                read_catalog_artwork(root)


if __name__ == '__main__':
    main()
