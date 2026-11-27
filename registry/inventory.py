"""Describe the exact members of a validated release and share identical file content."""
from hashlib import sha256
from pathlib import PurePosixPath

from package import write_json


def release_inventory(output, record, contents):
    members = []
    for name, data in sorted(contents.items()):
        digest = sha256(data).hexdigest()
        suffix = PurePosixPath(name).suffix.lower()
        if suffix == ".png" and data.startswith(b"\x89PNG\r\n\x1a\n"):
            ext = ".png"
        else:
            try:
                text = data.decode("utf-8")
                ext = ".txt" if "\x00" not in text else ".bin"
            except UnicodeDecodeError:
                ext = ".bin"
        url = f"content/{digest[:2]}/{digest}{ext}"
        path = output / url
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        members.append({"path": name, "size": len(data), "sha256": digest, "url": url})
    release = {"schema": 1, "package": record["slug"], "version": record["version"],
               "archiveSha256": record["sha256"], "files": members}
    manifest = f'api/v1/files/{record["slug"]}/{record["version"]}.json'
    write_json(output / manifest, release)
    return manifest, members
