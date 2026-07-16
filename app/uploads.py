"""Shared server-side upload validation for images and video.

Validity is always decided by decoding/inspecting the actual bytes — never
by trusting the client-supplied filename or Content-Type header.
"""

import io

from PIL import Image, UnidentifiedImageError

ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP"}

# (offset, magic bytes, container) — enough to positively identify a
# well-formed container without needing a full video-parsing library.
_VIDEO_SIGNATURES = (
    (4, b"ftyp"),          # ISO base media file format: mp4, mov, m4v
    (0, b"\x1a\x45\xdf\xa3"),  # EBML header: webm, mkv
)


class InvalidUploadError(ValueError):
    """Raised when an uploaded file fails server-side validation."""


def validate_image(file_storage, max_bytes):
    """Verify the upload is really an image and within the size limit.

    Returns the raw validated bytes on success; raises InvalidUploadError
    otherwise. Consumes and does not reset the file_storage stream.
    """
    raw = file_storage.read()
    if not raw:
        raise InvalidUploadError("Uploaded file is empty.")
    if len(raw) > max_bytes:
        raise InvalidUploadError(f"Image exceeds the {max_bytes // (1024 * 1024)} MB upload limit.")

    try:
        image = Image.open(io.BytesIO(raw))
        image_format = image.format
        image.verify()  # Raises if the file is corrupt or not an image.
    except (UnidentifiedImageError, OSError, SyntaxError) as exc:
        # SyntaxError: PIL's documented exception for some corrupt/truncated
        # files (e.g. a PNG with a bad chunk CRC) — without it, a malformed
        # upload 500s instead of failing validation cleanly.
        raise InvalidUploadError("File is not a valid image.") from exc

    if image_format not in ALLOWED_IMAGE_FORMATS:
        raise InvalidUploadError("Only JPEG, PNG, and WEBP images are allowed.")

    return raw


def validate_video(file_storage, max_bytes):
    """Verify the upload is really a video container and within the size limit.

    Returns the raw validated bytes on success; raises InvalidUploadError
    otherwise. Consumes and does not reset the file_storage stream.
    """
    raw = file_storage.read()
    if not raw:
        raise InvalidUploadError("Uploaded file is empty.")
    if len(raw) > max_bytes:
        raise InvalidUploadError(f"Video exceeds the {max_bytes // (1024 * 1024)} MB upload limit.")

    if not any(raw[offset : offset + len(magic)] == magic for offset, magic in _VIDEO_SIGNATURES):
        raise InvalidUploadError("Only MP4, MOV, and WEBM videos are allowed.")

    return raw
