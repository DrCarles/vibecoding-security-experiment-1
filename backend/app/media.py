import io
import os
import uuid
import warnings
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from PIL import Image, ImageOps

from .config import get_settings

ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP", "GIF"}
Image.MAX_IMAGE_PIXELS = 40_000_000

AVATAR_SIZE = 400
POST_MAX_SIDE = 1600


def media_url(path: str | None) -> str | None:
    return f"/media/{path}" if path else None


def save_image(upload: UploadFile, kind: str) -> str:
    """Validate an uploaded image, re-encode it as WebP and return its relative path.

    Re-encoding strips metadata (such as EXIF location) and guarantees we only ever
    serve a plain image, never the raw bytes the client sent.
    """
    s = get_settings()
    data = upload.file.read(s.max_upload_bytes + 1)
    if len(data) > s.max_upload_bytes:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, f"Image must be at most {s.max_upload_mb} MB")
    if not data:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Image file is empty")

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as probe:
                fmt = probe.format
                probe.verify()
            if fmt not in ALLOWED_FORMATS:
                raise ValueError(fmt)
            img = Image.open(io.BytesIO(data))
            img.load()
    except Exception:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Unsupported or corrupt image. Use JPEG, PNG, WebP or GIF."
        ) from None

    img = ImageOps.exif_transpose(img)
    has_alpha = "A" in img.getbands() or "transparency" in img.info
    img = img.convert("RGBA" if has_alpha else "RGB")
    if kind == "avatars":
        img = ImageOps.fit(img, (AVATAR_SIZE, AVATAR_SIZE), Image.Resampling.LANCZOS)
    else:
        img.thumbnail((POST_MAX_SIDE, POST_MAX_SIDE), Image.Resampling.LANCZOS)

    rel = f"{kind}/{uuid.uuid4().hex}.webp"
    dest = Path(s.media_dir) / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".tmp")
    img.save(tmp, "WEBP", quality=85, method=4)
    os.replace(tmp, dest)
    return rel


def delete_media(path: str | None) -> None:
    if not path:
        return
    root = Path(get_settings().media_dir).resolve()
    target = (root / path).resolve()
    if root not in target.parents:
        return
    target.unlink(missing_ok=True)
