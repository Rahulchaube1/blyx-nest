import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, main

from inventory import release_inventory


class InventoryTest(TestCase):
    def test_members_are_exact_and_content_is_shared(self):
        stamp = {"slug":"probe","version":"0.1.0","sha256":"0"*64}
        inputs = {"README.md":b"same\r\n","expected.txt":b"same\r\n","payload.bt":b"\xff\x00","empty.txt":b""}
        with TemporaryDirectory() as tmp:
            out = Path(tmp)
            url, files = release_inventory(out, stamp, inputs)
            self.assertTrue((out / url).exists())
            self.assertEqual(len(files), len(inputs))
            for f in files:
                raw = inputs[f["path"]]
                self.assertEqual(raw, (out/f["url"]).read_bytes())
                self.assertEqual(f["size"], len(raw))
                self.assertEqual(f["sha256"], hashlib.sha256(raw).hexdigest())
            self.assertEqual(sum(p.is_file() for p in (out/'content').rglob('*')), 3)
            self.assertTrue(next(f for f in files if f["path"]=="payload.bt")["url"].endswith(".bin"))

if __name__ == "__main__":
    main()
