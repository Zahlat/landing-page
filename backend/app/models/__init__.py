"""Import every model module here so Base.metadata knows about all tables
(Alembic autogenerate and the test suite rely on this)."""

from app.models.base import Base

__all__ = ["Base"]
