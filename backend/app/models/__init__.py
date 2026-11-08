"""Import every model module here so Base.metadata knows about all tables
(Alembic autogenerate and the test suite rely on this)."""

from app.models.admin_login_attempt import AdminLoginAttempt
from app.models.admin_session import AdminSession
from app.models.admin_user import AdminUser
from app.models.base import Base
from app.models.contact_message import ContactMessage

__all__ = ["AdminLoginAttempt", "AdminSession", "AdminUser", "Base", "ContactMessage"]
