"""Cloudinary storage for profile picture uploads.

Content-based validation itself lives in app/uploads.py, shared with the
memories blueprint's photo/video pipeline.
"""

import io

import cloudinary.uploader

from app.uploads import InvalidUploadError, validate_image

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
CLOUDINARY_FOLDER = "army_atlas/profile_pictures"
COVER_CLOUDINARY_FOLDER = "army_atlas/cover_photos"

# Re-exported for existing callers (app/blueprints/profiles/routes.py).
InvalidImageError = InvalidUploadError


def upload_profile_image(file_storage, previous_public_id=None, folder=CLOUDINARY_FOLDER):
    """Validate, upload to Cloudinary, then clean up the previous asset.

    The previous asset is only deleted after the new upload succeeds, so a
    failed upload never leaves the user without a picture. Shared by the
    avatar and cover-photo pickers (app/blueprints/profiles/routes.py) —
    `folder` just separates the two in Cloudinary.
    """
    raw = validate_image(file_storage, MAX_UPLOAD_BYTES)

    result = cloudinary.uploader.upload(
        io.BytesIO(raw),
        folder=folder,
        resource_type="image",
    )

    if previous_public_id:
        cloudinary.uploader.destroy(previous_public_id, resource_type="image")

    return result["secure_url"], result["public_id"]
