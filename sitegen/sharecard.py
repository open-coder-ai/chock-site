"""The link-preview image (og:image): its type and pixel size, read from the PNG file itself."""

import struct
from pathlib import Path

from .pageparts import PageError

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def image_size(static_dir: Path, og_image: str) -> dict[str, object]:
    """Type, width and height of the site-relative PNG `og_image`; any other file is an error."""
    if not og_image.startswith("/") or og_image.startswith("//"):
        raise PageError(f"site.json og_image {og_image!r} must be a path on this site")
    path = static_dir / og_image.lstrip("/")
    if not path.is_file():
        raise PageError(f"site.json og_image {og_image!r} is not a file under static/")
    head = path.read_bytes()[:24]
    if len(head) < 24 or head[:8] != PNG_SIGNATURE or head[12:16] != b"IHDR":
        raise PageError(f"site.json og_image {og_image!r} is not a PNG file")
    width, height = struct.unpack(">II", head[16:24])
    return {"type": "image/png", "width": width, "height": height}
