"""
Database operations for the manga scraper.

This module combines the scraper with database operations to store
scraped manga information, chapters, and images.
"""

from scraper import SearchResultsScraper, MangaDetailsScarper, ChapterImagesScraper, SerieScraper
from database import Database
import os
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class MangaDownloader:
    """Class for downloading manga and storing in the database."""

    def __init__(self, db_path: str = "sqlite:///manga.db", download_dir: str = "downloads"):
        """
        Initialize the manga downloader.

        Args:
            db_path: Path to the database
            download_dir: Directory to store downloaded files
        """
        self.db = Database(db_path)
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(parents=True, exist_ok=True)
        
        # Create subdirectories
        self.manga_dir = self.download_dir / "manga"
        self.chapters_dir = self.download_dir / "chapters"
        self.images_dir = self.download_dir / "images"
        
        for directory in [self.manga_dir, self.chapters_dir, self.images_dir]:
            directory.mkdir(exist_ok=True)

    def download_manga(self, manga_url: str) -> bool:
        """
        Download manga information and save to database.

        Args:
            manga_url: URL of the manga to download

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Scrape manga details
            scraper = MangaDetailsScarper(manga_url)
            details = scraper.details

            # Prepare manga data
            manga_data = {
                'url': manga_url,
                'title': details.title,
                'poster_url': details.poster,
                'description': details.description,
                'genres': details.genres,
                'status': details.status,
                'rate': float(details.rate)
            }

            # Save to database
            manga = self.db.save_manga(manga_data)
            logger.info(f"Saved manga: {manga.title}")

            # Save all chapters
            for chapter in details.chapters:
                chapter_data = {
                    'url': chapter.url,
                    'title': chapter.title,
                    'order_no': chapter.order_no
                }
                self.db.save_chapter(manga_url, chapter_data)
            
            logger.info(f"Saved {len(details.chapters)} chapters")
            return True
            
        except Exception as e:
            logger.error(f"Error downloading manga {manga_url}: {str(e)}")
            return False

    def download_chapter(self, chapter_url: str, download_images: bool = False) -> bool:
        """
        Download chapter and optionally its images.

        Args:
            chapter_url: URL of the chapter to download
            download_images: Whether to download the images

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Get chapter images
            scraper = ChapterImagesScraper(chapter_url)
            
            # Save image information to database
            images_data = [
                {'url': img.url, 'order_no': img.order_no}
                for img in scraper.images
            ]
            saved_images = self.db.save_chapter_images(chapter_url, images_data)
            
            if download_images:
                # Create chapter directory
                chapter_dir = self.chapters_dir / Path(chapter_url).name
                chapter_dir.mkdir(exist_ok=True)
                
                # Download as PDF
                pdf_path = str(chapter_dir / "chapter.pdf")
                scraper.download_images_as_pdf(pdf_path)
                
                # Update database
                self.db.update_chapter_download_status(chapter_url, pdf_path)
                
                for image in saved_images:
                    # The images are already downloaded and included in the PDF
                    # Just update their status
                    self.db.update_image_download_status(
                        chapter_url,
                        image.order_no,
                        str(chapter_dir / f"page_{image.order_no}.jpg")
                    )
            
            logger.info(f"Saved chapter with {len(saved_images)} images")
            return True
            
        except Exception as e:
            logger.error(f"Error downloading chapter {chapter_url}: {str(e)}")
            return False

    def download_all_chapters(self, manga_url: str, download_images: bool = False) -> bool:
        """
        Download all chapters for a manga.

        Args:
            manga_url: URL of the manga
            download_images: Whether to download chapter images

        Returns:
            bool: True if all chapters were downloaded successfully
        """
        try:
            # First ensure we have manga information
            scraper = MangaDetailsScarper(manga_url)
            details = scraper.details
            
            # Download each chapter
            success = True
            for chapter in details.chapters:
                if not self.download_chapter(chapter.url, download_images):
                    success = False
                    logger.error(f"Failed to download chapter: {chapter.title}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error downloading chapters for {manga_url}: {str(e)}")
            return False

    def search_and_download(self, search_term: str, download_chapters: bool = False) -> bool:
        """
        Search for manga and download results.

        Args:
            search_term: Term to search for
            download_chapters: Whether to download chapters

        Returns:
            bool: True if all operations were successful
        """
        try:
            # Search for manga
            search = SearchResultsScraper(search_term)
            search.prepare_results()
            
            # Download each manga found
            success = True
            for result in search.results:
                if not self.download_manga(result.url):
                    success = False
                    continue
                    
                if download_chapters:
                    if not self.download_all_chapters(result.url):
                        success = False
            
            return success
            
        except Exception as e:
            logger.error(f"Error in search and download for '{search_term}': {str(e)}")
            return False

def main():
    """Example usage of the MangaDownloader."""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Initialize downloader
    downloader = MangaDownloader()
    
    # Example: Search and download manga
    search_term = "one piece"
    logger.info(f"Searching for: {search_term}")
    downloader.search_and_download(search_term, download_chapters=True)

if __name__ == "__main__":
    main()