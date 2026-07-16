"""Cloudinary storage for memory photos/videos.

Content-based validation itself lives in app/uploads.py, shared with the
profile picture pipeline. Each upload is tried as an image first, then a
video — never trusting the client's filename or declared content-type.
"""

import io

import cloudinary.uploader

from app.uploads import InvalidUploadError, validate_image, validate_video

MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_VIDEO_BYTES = 25 * 1024 * 1024
MAX_FILES_PER_MEMORY = 6
CLOUDINARY_FOLDER = "army_atlas/memories"


def upload_memory_media(file_storage):
    """Validate one uploaded file by content and push it to Cloudinary.

    Returns (url, public_id, media_type) where media_type is "image" or
    "video". Raises InvalidUploadError if the file is neither.
    """
    try:
        raw = validate_image(file_storage, MAX_IMAGE_BYTES)
        media_type = "image"
    except InvalidUploadError:
        file_storage.seek(0)
        try:
            raw = validate_video(file_storage, MAX_VIDEO_BYTES)
            media_type = "video"
        except InvalidUploadError:
            name = file_storage.filename or "File"
            raise InvalidUploadError(f"{name} is not a supported image or video.") from None

    result = cloudinary.uploader.upload(
        io.BytesIO(raw), folder=CLOUDINARY_FOLDER, resource_type=media_type
    )
    return result["secure_url"], result["public_id"], media_type


def delete_memory_media(public_id, media_type):
    cloudinary.uploader.destroy(public_id, resource_type=media_type)
