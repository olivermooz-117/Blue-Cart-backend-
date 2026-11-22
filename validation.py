"""Request validation helpers and the application error type."""

import re
from math import isfinite

from flask import request

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class ApiError(Exception):
    """Carries a human-readable message and an HTTP status code."""

    def __init__(self, message, status=400):
        super().__init__(message)
        self.message = message
        self.status = status


def get_json_object():
    """Return the parsed JSON body as a dict, or raise ApiError(400)."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ApiError("Request body must be a JSON object", 400)
    return data


def clean_str(value, field, max_len, required=True):
    """Coerce a form/body field to a stripped string of bounded length.

    Rejects non-strings (unless required=False and value is None), strips
    whitespace, and enforces the maximum length.
    """
    if value is None:
        if required:
            raise ApiError(f"{field} is required", 400)
        return ""
    if not isinstance(value, str):
        raise ApiError(f"{field} must be a string", 400)
    cleaned = value.strip()
    if required and not cleaned:
        raise ApiError(f"{field} is required", 400)
    if len(cleaned) > max_len:
        raise ApiError(f"{field} must be at most {max_len} characters", 400)
    return cleaned
