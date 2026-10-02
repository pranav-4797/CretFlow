"""
Core module __init__ — exports key dependencies for convenient importing.
"""

from app.core.config import settings, get_settings
from app.core.security import get_current_user, get_optional_user, AuthenticatedUser


__all__ = [
    "settings",
    "get_settings",
    "get_current_user",
    "get_optional_user",
    "AuthenticatedUser",
]
