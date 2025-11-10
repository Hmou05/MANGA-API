"""
SQLAlchemy ORM models for manga database.

This module defines the database schema using SQLAlchemy ORM,
providing models for Manga, Genre, Chapter, and ChapterImage entities.
"""

from sqlalchemy import Column, String, Float, Text, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

Base = declarative_base()

def get_uuid() -> str:
    """
    Generate a UUID string.
    
    Returns:
        str: UUID in hexadecimal format
    """
    return str(uuid.uuid4())

class MangaDB(Base):
    """Database model for manga information."""
    __tablename__ = "manga"
    
    id = Column(String(36), primary_key=True, default=get_uuid)
    title = Column(String(255), nullable=False, index=True)
    url = Column(String(500), unique=True, nullable=False, index=True)
    poster = Column(String(500))
    description = Column(Text)
    status = Column(String(50))
    rate = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    genres = relationship("GenreDB", back_populates="manga", cascade="all, delete-orphan")
    chapters = relationship("ChapterDB", back_populates="manga", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<MangaDB(id={self.id}, title='{self.title}')>"

class GenreDB(Base):
    """Database model for manga genres."""
    __tablename__ = "genre"
    
    id = Column(String(36), primary_key=True, default=get_uuid)
    manga_id = Column(String(36), ForeignKey("manga.id"), nullable=False)
    name = Column(String(100), nullable=False, index=True)
    
    # Relationships
    manga = relationship("MangaDB", back_populates="genres")
    
    def __repr__(self):
        return f"<GenreDB(id={self.id}, name='{self.name}')>"

class ChapterDB(Base):
    """Database model for manga chapters."""
    __tablename__ = "chapter"
    
    id = Column(String(36), primary_key=True, default=get_uuid)
    manga_id = Column(String(36), ForeignKey("manga.id"), nullable=False)
    order_no = Column(String, nullable=False)
    title = Column(String(255), nullable=False)
    url = Column(String(500), unique=True, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    manga = relationship("MangaDB", back_populates="chapters")
    images = relationship("ChapterImageDB", back_populates="chapter", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<ChapterDB(id={self.id}, title='{self.title}')>"

class ChapterImageDB(Base):
    """Database model for chapter images."""
    __tablename__ = "chapter_image"
    
    id = Column(String(36), primary_key=True, default=get_uuid)
    chapter_id = Column(String(36), ForeignKey("chapter.id"), nullable=False)
    order_no = Column(String, nullable=False)
    url = Column(String(500), nullable=False)
    
    # Relationships
    chapter = relationship("ChapterDB", back_populates="images")
    
    def __repr__(self):
        return f"<ChapterImageDB(id={self.id}, order_no={self.order_no})>"
