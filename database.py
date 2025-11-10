"""
Database module for storing manga data.

This module handles all database operations including:
- Storing manga information
- Managing chapters
- Caching image locations
- Tracking download status
"""

from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, Table, Text, LargeBinary, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy.sql import func
from datetime import datetime
from typing import List, Optional
import os
import io
from PIL import Image
import img2pdf
import warnings

# Suppress SQLAlchemy warnings about TypeDecorator
warnings.filterwarnings('ignore', category=UserWarning)

# Create base class for declarative models
Base = declarative_base()

# Create engine
DB_PATH = os.path.join(os.path.dirname(__file__), 'manga.db')
engine = create_engine(f'sqlite:///{DB_PATH}')

# Create session factory
Session = sessionmaker(bind=engine)

# Create all tables
def init_db():
    Base.metadata.create_all(engine)

# Define association table for manga-genre relationship
manga_genres = Table(
    'manga_genres',
    Base.metadata,
    Column('manga_id', Integer, ForeignKey('mangas.id'), primary_key=True),
    Column('genre_id', Integer, ForeignKey('genres.id'), primary_key=True)
)

class Genre(Base):
    """Genre model for categorizing manga."""
    __tablename__ = 'genres'

    id = Column(Integer, primary_key=True)
    name = Column(String(50), unique=True, nullable=False)
    mangas = relationship('Manga', secondary=manga_genres, back_populates='genres')

    def __repr__(self):
        return f"<Genre {self.name}>"

class Manga(Base):
    """Manga model storing basic information about a manga series."""
    __tablename__ = 'mangas'

    id = Column(Integer, primary_key=True)
    url = Column(String(255), unique=True, nullable=False)
    title = Column(String(255), nullable=False)
    poster_url = Column(String(255))
    poster_image = Column(LargeBinary)  # Store poster image as binary
    poster_mime_type = Column(String(50))  # Store image MIME type
    description = Column(Text)
    status = Column(String(50))
    rate = Column(Float)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    genres = relationship('Genre', secondary=manga_genres, back_populates='mangas')
    chapters = relationship('Chapter', back_populates='manga', cascade='all, delete-orphan')

    def __repr__(self):
        return f"<Manga {self.title}>"
        
    def set_poster_from_bytes(self, image_bytes: bytes, mime_type: str):
        """Set the poster image from bytes."""
        self.poster_image = image_bytes
        self.poster_mime_type = mime_type
        
    def get_poster_image(self) -> Optional[bytes]:
        """Get the poster image bytes."""
        return self.poster_image if self.poster_image else None

class Chapter(Base):
    """Chapter model storing chapter information and download status."""
    __tablename__ = 'chapters'

    id = Column(Integer, primary_key=True)
    manga_id = Column(Integer, ForeignKey('mangas.id'), nullable=False)
    url = Column(String(255), unique=True, nullable=False)
    title = Column(String(255), nullable=False)
    order_no = Column(Integer, nullable=False)
    pdf_path = Column(String(255))  # Path to downloaded PDF
    is_downloaded = Column(Integer, default=0)  # 0: not downloaded, 1: downloaded
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    manga = relationship('Manga', back_populates='chapters')
    images = relationship('ChapterImage', back_populates='chapter', cascade='all, delete-orphan')

    def __repr__(self):
        return f"<Chapter {self.manga.title} - {self.title}>"
        
    def get_ordered_images(self) -> List['ChapterImage']:
        """Get chapter images ordered by order_no."""
        return sorted(self.images, key=lambda x: x.order_no)
        
    def generate_pdf(self) -> bytes:
        """Generate PDF from chapter images."""
        image_list = []
        for chapter_image in self.get_ordered_images():
            if chapter_image.image_data:
                img = Image.open(io.BytesIO(chapter_image.image_data))
                image_bytes = io.BytesIO()
                img.save(image_bytes, format='JPEG')
                image_list.append(image_bytes.getvalue())
        
        pdf_bytes = io.BytesIO()
        if image_list:
            img2pdf.convert(image_list, outputstream=pdf_bytes)
        return pdf_bytes.getvalue()

class ChapterImage(Base):
    """Model for storing chapter image information and binary data."""
    __tablename__ = 'chapter_images'

    id = Column(Integer, primary_key=True)
    chapter_id = Column(Integer, ForeignKey('chapters.id'), nullable=False)
    url = Column(String(255), nullable=False)
    image_data = Column(LargeBinary)  # Store image as binary
    mime_type = Column(String(50))  # Store image MIME type
    order_no = Column(Integer, nullable=False)
    is_downloaded = Column(Integer, default=0)  # 0: not downloaded, 1: downloaded
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Indexes for better performance
    __table_args__ = (
        Index('idx_chapter_order', 'chapter_id', 'order_no'),
    )
    
    def set_image_from_bytes(self, image_bytes: bytes, mime_type: str):
        """Set the image data from bytes."""
        self.image_data = image_bytes
        self.mime_type = mime_type
        self.is_downloaded = 1
    
    def get_image(self) -> Optional[bytes]:
        """Get the image bytes."""
        return self.image_data if self.image_data else None
        
    def __repr__(self):
        return f"<ChapterImage {self.chapter_id} - {self.order_no}>"
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    chapter = relationship('Chapter', back_populates='images')

    def __repr__(self):
        return f"<ChapterImage {self.chapter.title} - Page {self.order_no}>"

class Database:
    """Database manager class for handling all database operations."""

    def __init__(self, db_path: str = "sqlite:///manga.db"):
        """
        Initialize database connection.

        Args:
            db_path: Database URL (defaults to SQLite database in current directory)
        """
        self.engine = create_engine(db_path)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def save_manga(self, manga_data: dict) -> Manga:
        """
        Save or update manga information.

        Args:
            manga_data: Dictionary containing manga information
                Required keys: url, title
                Optional keys: poster_url, genres, description, status, rate

        Returns:
            Manga: Saved manga instance
        """
        session = self.Session()
        try:
            manga = session.query(Manga).filter_by(url=manga_data['url']).first()
            if not manga:
                manga = Manga(
                    url=manga_data['url'],
                    title=manga_data['title']
                )
                session.add(manga)

            # Update fields
            manga.title = manga_data['title']
            manga.poster_url = manga_data.get('poster_url')
            manga.description = manga_data.get('description')
            manga.status = manga_data.get('status')
            manga.rate = manga_data.get('rate')

            # Handle genres
            if 'genres' in manga_data:
                existing_genres = []
                for genre_name in manga_data['genres']:
                    genre = session.query(Genre).filter_by(name=genre_name).first()
                    if not genre:
                        genre = Genre(name=genre_name)
                        session.add(genre)
                    existing_genres.append(genre)
                manga.genres = existing_genres

            session.commit()
            return manga
        finally:
            session.close()

    def save_chapter(self, manga_url: str, chapter_data: dict) -> Chapter:
        """
        Save or update chapter information.

        Args:
            manga_url: URL of the parent manga
            chapter_data: Dictionary containing chapter information
                Required keys: url, title, order_no

        Returns:
            Chapter: Saved chapter instance
        """
        session = self.Session()
        try:
            manga = session.query(Manga).filter_by(url=manga_url).first()
            if not manga:
                raise ValueError(f"Manga with URL {manga_url} not found")

            chapter = session.query(Chapter).filter_by(url=chapter_data['url']).first()
            if not chapter:
                chapter = Chapter(
                    manga_id=manga.id,
                    url=chapter_data['url'],
                    title=chapter_data['title'],
                    order_no=chapter_data['order_no']
                )
                session.add(chapter)
            else:
                chapter.title = chapter_data['title']
                chapter.order_no = chapter_data['order_no']

            session.commit()
            return chapter
        finally:
            session.close()

    def save_chapter_images(self, chapter_url: str, images_data: List[dict]) -> List[ChapterImage]:
        """
        Save chapter image information.

        Args:
            chapter_url: URL of the parent chapter
            images_data: List of dictionaries containing image information
                Required keys for each image: url, order_no

        Returns:
            List[ChapterImage]: List of saved image instances
        """
        session = self.Session()
        try:
            chapter = session.query(Chapter).filter_by(url=chapter_url).first()
            if not chapter:
                raise ValueError(f"Chapter with URL {chapter_url} not found")

            saved_images = []
            for img_data in images_data:
                image = session.query(ChapterImage).filter_by(
                    chapter_id=chapter.id,
                    order_no=img_data['order_no']
                ).first()

                if not image:
                    image = ChapterImage(
                        chapter_id=chapter.id,
                        url=img_data['url'],
                        order_no=img_data['order_no']
                    )
                    session.add(image)
                else:
                    image.url = img_data['url']

                saved_images.append(image)

            session.commit()
            return saved_images
        finally:
            session.close()

    def update_chapter_download_status(self, chapter_url: str, pdf_path: str):
        """
        Update chapter's download status and PDF path.

        Args:
            chapter_url: URL of the chapter
            pdf_path: Path to the downloaded PDF file
        """
        session = self.Session()
        try:
            chapter = session.query(Chapter).filter_by(url=chapter_url).first()
            if chapter:
                chapter.pdf_path = pdf_path
                chapter.is_downloaded = 1
                session.commit()
        finally:
            session.close()

    def update_image_download_status(self, chapter_url: str, order_no: int, local_path: str):
        """
        Update image's download status and local path.

        Args:
            chapter_url: URL of the parent chapter
            order_no: Order number of the image
            local_path: Path to the downloaded image
        """
        session = self.Session()
        try:
            chapter = session.query(Chapter).filter_by(url=chapter_url).first()
            if chapter:
                image = session.query(ChapterImage).filter_by(
                    chapter_id=chapter.id,
                    order_no=order_no
                ).first()
                if image:
                    image.local_path = local_path
                    image.is_downloaded = 1
                    session.commit()
        finally:
            session.close()