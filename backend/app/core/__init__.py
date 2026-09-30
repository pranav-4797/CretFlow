"""
Core module __init__ — exports key dependencies for convenient importing.
"""

from app.core.config import settings, get_settings
from app.core.security import get_current_user, get_optional_user, AuthenticatedUser

# Database imports are lazy — SQLAlchemy is only required from Phase 3 onwards.
# Import directly from app.core.database when needed:
#   from app.core.database import get_db, Base

__all__ = [
    "settings",
    "get_settings",
    "get_current_user",
    "get_optional_user",
    "AuthenticatedUser",
]
