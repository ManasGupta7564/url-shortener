from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime
from sqlalchemy.sql import func

from app.database import Base


class URL(Base):
    __tablename__ = "urls"

    id = Column(Integer, primary_key=True, index=True)
    short_code = Column(String(10), unique=True, nullable=False, index=True)
    original_url = Column(Text, nullable=False)
    expires_at = Column(DateTime, nullable=True)

class Click(Base):
    __tablename__ = "clicks"

    id = Column(Integer, primary_key=True, index=True)

    url_id = Column(
        Integer,
        ForeignKey("urls.id"),
        nullable=False,
        index=True
    )

    clicked_at = Column(
        DateTime,
        server_default=func.now(),
        nullable=False
    )

    referrer = Column(String(500), nullable=True)

    user_agent = Column(String(500), nullable=True)