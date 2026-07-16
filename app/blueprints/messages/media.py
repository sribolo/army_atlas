"""Cloudinary storage for message image attachments.

Content-based validation itself lives in app/uploads.py, shared with the
profile picture and memories photo/video pipelines. One optional image per
message — no video attachments here.
"""

import io

import cloudinary.uploader

from app.uploads import validate_image

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
CLOUDINARY_FOLDER = "army_atlas/messages"


def upload_message_image(file_storage):
    """Validate then upload to Cloudinary. Returns (url, public_id)."""
    raw = validate_image(file_storage, MAX_UPLOAD_BYTES)
    result = cloudinary.uploader.upload(
        io.BytesIO(raw), folder=CLOUDINARY_FOLDER, resource_type="image"
    )
    return result["secure_url"], result["public_id"]


def delete_message_image(public_id):
    cloudinary.uploader.destroy(public_id, resource_type="image")