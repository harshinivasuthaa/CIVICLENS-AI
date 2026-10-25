import os
import uuid
from pathlib import Path
from werkzeug.utils import secure_filename
from flask import current_app

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "pdf"}


def allowed_file(filename: str) -> bool:
    """Verifies file extension against the whitelist."""
    if "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in ALLOWED_EXTENSIONS


def save_quarantined_upload(file_storage) -> str:
    """
    Saves an uploaded file to the designated quarantine directory with a randomized UUID prefix.
    Returns the relative stored path.
    """
    if not file_storage or not file_storage.filename:
        return None

    filename = secure_filename(file_storage.filename)
    if not allowed_file(filename):
        raise ValueError(f"Disallowed file type. Allowed extensions: {', '.join(ALLOWED_EXTENSIONS)}")

    # Ensure quarantine directory exists
    upload_folder = Path(current_app.config["UPLOAD_FOLDER"])
    upload_folder.mkdir(parents=True, exist_ok=True)

    # Generate a collision-resistant UUID filename
    ext = filename.rsplit(".", 1)[1].lower()
    unique_name = f"{uuid.uuid4().hex}_{filename[:32]}.{ext}"
    target_path = upload_folder / unique_name

    file_storage.save(str(target_path))
    return unique_name
