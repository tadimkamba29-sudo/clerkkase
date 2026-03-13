"""
Authentication package for ClerKase.
"""

from .utils import (
    hash_password,
    verify_password,
    validate_password_strength,
    create_access_token,
    create_refresh_token,
    decode_token,
    extract_bearer_token,
)
from .decorators import login_required, optional_auth

__all__ = [
    "hash_password",
    "verify_password",
    "validate_password_strength",
    "create_access_token",
    "create_refresh_token",
    "decode_token",
    "extract_bearer_token",
    "login_required",
    "optional_auth",
]
