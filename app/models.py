from sqlalchemy import Column, Integer, String, Text
from app.database import Base


class URL(Base):
    __tablename__ = "urls"

    id = Column(Integer, primary_key=True, index=True)
    short_code = Column(String(10), unique=True, nullable=False, index=True)
    original_url = Column(Text, nullable=False)