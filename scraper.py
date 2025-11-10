"""
Manga Scraping API

This module provides a comprehensive set of tools for scraping manga information, chapters, and images.
It includes functionality for searching manga titles, getting detailed information, extracting chapters,
downloading images, and browsing available series.

Key Features:
- Search for manga titles with detailed results
- Extract manga details including description, genres, and chapters
- Download chapter images and convert to PDF
- Browse all available manga series
- Built-in retry mechanism for network requests
- Concurrent downloads with thread pooling
- Automatic resource cleanup
- Database integration to save manga data
- Progress tracking with terminal progress bars
- File-based logging with Unicode support

Dependencies:
- requests: For HTTP requests with retry capabilities
- selectolax: For HTML parsing
- img2pdf: For converting images to PDF
- SQLAlchemy: For database interaction
- tqdm: For progress bar visualization
"""

import logging
from functools import cached_property
from models import MangaSearchResult, ChapterLatest, ChapterDetailed, MangaDetails, ChapterImage
from typing import List, Set
import requests
from selectolax.lexbor import LexborHTMLParser, LexborNode
import img2pdf
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import tempfile
from database import get_db_session, close_db_session, init_db
from db_models import MangaDB, GenreDB, ChapterDB, ChapterImageDB, get_uuid
from sqlalchemy.exc import IntegrityError
from tqdm import tqdm

# Configure logging to file only with UTF-8 encoding
def setup_logging():
    """Configure logging to write to a file with UTF-8 encoding."""
    log_file = Path(__file__).parent / "scraper.log"
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8')
        ]
    )

setup_logging()
logger = logging.getLogger(__name__)

# Global session instance for connection pooling and retry handling
_session = None

def get_session(retries: int = 3, backoff_factor: float = 0.3, status_forcelist=(500, 502, 504)) -> requests.Session:
    """
    Get or create a shared requests Session with retry capabilities.

    This function maintains a single global session for connection pooling and
    configures it with automatic retries for failed requests. The session uses
    exponential backoff between retries and retries only on specific HTTP status codes.

    Args:
        retries (int): Maximum number of retries for failed requests
        backoff_factor (float): Factor to calculate delay between retries
            {delay} = backoff_factor * (2 ** ({retry number} - 1))
        status_forcelist (tuple): HTTP status codes that should trigger a retry

    Returns:
        requests.Session: Configured session object with retry capabilities
        
    Example:
        >>> session = get_session(retries=5, backoff_factor=0.5)
        >>> response = session.get('https://example.com')
    """
    global _session
    if _session is None:
        s = requests.Session()
        retry = Retry(total=retries, backoff_factor=backoff_factor,
                      status_forcelist=status_forcelist, allowed_methods=frozenset(['GET', 'POST']))
        adapter = HTTPAdapter(max_retries=retry)
        s.mount("https://", adapter)
        s.mount("http://", adapter)
        s.headers.update({"User-Agent": "mangaha-api/1.0 (+https://example.com)"})
        _session = s
    return _session

def get_content(url: str, params: dict | None = None, timeout: float = 10.0) -> bytes:
    """
    Fetch raw content from a URL with optional parameters.

    This function uses the shared session with retry capabilities to fetch content.
    It handles query parameters and enforces a timeout for the request.

    Args:
        url (str): The URL to fetch content from
        params (dict, optional): Query parameters to include in the request
        timeout (float): Request timeout in seconds

    Returns:
        bytes: Raw content from the URL

    Raises:
        requests.RequestException: If the request fails after all retries
        requests.Timeout: If the request times out
        
    Example:
        >>> content = get_content('https://example.com/image.jpg', timeout=5.0)
        >>> with open('image.jpg', 'wb') as f:
        ...     f.write(content)
    """
    if params is None:
        params = {}
    session = get_session()
    resp = session.get(url, params=params, timeout=timeout, stream=True)
    resp.raise_for_status()
    return resp.content

def get_html(url: str, params: dict | None = None, timeout: float = 10.0) -> LexborHTMLParser:
    """
    Fetch and parse HTML content from a URL.

    This function combines get_content() with HTML parsing using selectolax.
    The parsed document allows for easy CSS selector-based content extraction.

    Args:
        url (str): The URL to fetch HTML from
        params (dict, optional): Query parameters to include in the request
        timeout (float): Request timeout in seconds

    Returns:
        LexborHTMLParser: Parsed HTML document object

    Raises:
        requests.RequestException: If the request fails after all retries
        requests.Timeout: If the request times out
        
    Example:
        >>> doc = get_html('https://example.com')
        >>> title = doc.css_first('h1').text()
    """
    src = get_content(url, params=params, timeout=timeout)
    return LexborHTMLParser(src)

class SearchResultsScraper:
    """
    Search for manga titles and handle search results.

    This class manages the search process, including pagination and result parsing.
    It fetches results from all available pages and provides easy access to the
    parsed manga information.

    Attributes:
        MAX_RESULTS_PER_PAGE (int): Maximum results shown per page (12)
        search (str): Search query string
        result_no (int): Total number of results found
        pages (int): Total number of result pages
        result_nodes (List[LexborHTMLParser]): Raw HTML nodes containing results
        results (List[MangaSearchResult]): Parsed search results

    Example:
        >>> scraper = SearchResultsScraper("one piece")
        >>> scraper.prepare_results()
        >>> for manga in scraper.results:
        ...     print(f"{manga.title}: {manga.latest_chapter.title}")
    """
    
    MAX_RESULTS_PER_PAGE = 12
    
    def __init__(self, search: str) :
        """
        Initialize the search scraper.

        Args:
            search (str): Search query string to look for manga titles
        """
        self.search = search
        self.result_no = 0
        self.pages = 1
        self.result_nodes: List[LexborHTMLParser] = []
        self.results: List[MangaSearchResult] = []
        
    def post_result_nodes(self) :
        """
        Fetch and store raw HTML nodes containing search results.

        This method fetches the first page of results and determines the total number
        of pages. If there are multiple pages, it fetches all remaining pages.
        The raw HTML nodes are stored for later parsing.
        """
        html = get_html("https://azoramoon.com/", {"s": self.search, "post_type": "wp-manga"})
        try :
            self.result_no = int(html.css_first("h1").text(strip=True).split(" ")[0])
            self.pages = self.result_no // SearchResultsScraper.MAX_RESULTS_PER_PAGE + 1
            self.result_nodes += html.css("div.row.c-tabs-item__content")
            if self.pages > 1:
                for i in range(2, self.pages + 1):
                    html = get_html(f"https://azoramoon.com/page{i}/", {"s": self.search, "post_type": "wp-manga"})
                    self.result_nodes += html.css("div.row.c-tabs-item__content")
            logger.debug("Found %d results across %d pages for search: %s", self.result_no, self.pages, self.search)
        except AttributeError :
            self.result_no = 0
            self.pages = 0
            self.result_nodes = []
            logger.debug("No results found for search: %s", self.search)
    
    def get_result(self, result_node: LexborNode) -> MangaSearchResult:
        """
        Parse a single search result node into a MangaSearchResult object.

        This method extracts all relevant information from the HTML node including
        title, URL, cover image, genres, status, rating, and latest chapter.

        Args:
            result_node (LexborNode): HTML node containing the manga information

        Returns:
            MangaSearchResult: Parsed manga search result
        """
        side_node = result_node.css_first("div.c-image-hover a")
        url = side_node.attrs["href"]
        title = side_node.attrs["title"]
        poster = side_node.css_first("img").attrs["src"]
        del side_node
        genres = [genre_node.text(strip=True) for genre_node in result_node.css("div.mg_genres div.summary-content a")]
        status = result_node.css_first("div.mg_status div.summary-content").text(strip=True)
        rate = float(result_node.css_first("span.total_votes").text(strip=True))
        latest_chapter_node = result_node.css_first("div.latest-chap a")
        latest_chapter: ChapterLatest = ChapterLatest(
            url=latest_chapter_node.attrs["href"],
            title=latest_chapter_node.text(strip=True)
        )
        del latest_chapter_node
        result = MangaSearchResult(
            url=url,
            title=title,
            poster=poster,
            genres=genres,
            status=status,
            rate=rate,
            latest_chapter=latest_chapter
        )
        return result
    
    def post_results(self):
        """
        Parse all result nodes into MangaSearchResult objects.

        This method processes all the raw HTML nodes collected by post_result_nodes()
        and converts them into MangaSearchResult objects for easy access to the data.
        """
        self.results += [self.get_result(node) for node in self.result_nodes]
    
    def prepare_results(self):
        """
        Main method to fetch and prepare all search results.

        This method orchestrates the entire search process by:
        1. Fetching all result pages
        2. Parsing the HTML nodes
        3. Converting them into MangaSearchResult objects

        Use this method to perform the search and access results.
        """
        self.post_result_nodes()
        self.post_results()

class MangaDetailsScarper:
    """
    Scrape detailed information about a manga.

    This class handles the extraction of all detailed information about a manga,
    including its metadata, description, chapters, and more. It provides properties
    for easy access to each piece of information.

    Attributes:
        manga_url (str): URL of the manga to scrape
        page (LexborHTMLParser): Parsed HTML document of the manga page

    Example:
        >>> scraper = MangaDetailsScarper("https://example.com/manga/1")
        >>> details = scraper.details
        >>> print(f"{details.title} ({details.status})")
        >>> print(f"Genres: {', '.join(details.genres)}")
    """

    def __init__(self, manga_url: str) -> None:
        """
        Initialize the manga details scraper.

        Args:
            manga_url (str): URL of the manga to scrape
        """
        self.manga_url = manga_url
        self.page = get_html(manga_url)
    
    @property
    def title(self) -> str:
        """
        Get the manga title.

        Returns:
            str: The manga's title
        """
        title = self.page.css_first("h1").text(strip=True) or "Unknown Title"
        return title
    
    @property
    def poster(self) -> str:
        """
        Get the manga cover image URL.

        Returns:
            str: URL of the cover image
        """
        try :
            poster = self.page.css_first("div.summary_image a img.img-responsive").attrs["src"]
        except AttributeError :
            poster = "https://placehold.it/150x200"
        return poster
    
    @property
    def description(self) -> str:
        """
        Get the manga description.

        Returns:
            str: Full description/summary of the manga
        """
        try :
            description = self.page.css_first("div.manga-summary").text(strip=True)
        except AttributeError :
            description = "No description available."
        return description
    
    @property
    def genres(self) -> List[str]:
        """
        Get the list of manga genres.

        Returns:
            List[str]: List of genre names
        """
        try :
            genres = [node.text(strip=True) for node in self.page.css("div.genres-content a")]
        except AttributeError :
            genres = []
        return genres
    
    @property
    def status(self) -> str:
        """
        Get the manga publication status.

        Returns:
            str: Publication status (e.g., "Ongoing", "Completed")
        """
        try :
            status = self.page.css_first("div.summary-content div.tags-content").text(strip=True)
        except AttributeError :
            status = "Unknown"
        return status
    
    @property
    def rate(self) -> float:
        """
        Get the manga rating.

        Returns:
            float: Average rating of the manga
        """
        try :
            rate = self.page.css_first("span#averagerate").text(strip=True)
        except AttributeError :
            rate = 0.0
        return rate
    
    @property
    def chapters(self) -> List[ChapterDetailed]:
        """
        Get the list of manga chapters.

        Returns a list of chapters in chronological order (oldest to newest).
        Each chapter includes its order number, URL, and title.

        Returns:
            List[ChapterDetailed]: List of chapter objects
        """
        try :
            chapter_nodes = self.page.css("li.wp-manga-chapter")[::-1]
            if not chapter_nodes :
                chapters = [
                    ChapterDetailed(
                        order_no=n,
                        url=chapter_node.css_first("a").attrs["href"],
                        title=chapter_node.css_first("a").text(strip=True)
                    ) for n, chapter_node in enumerate(chapter_nodes)
                ]
                return chapters
        except AttributeError :
            pass
        return []

    @property
    def details(self) -> MangaDetails:
        """
        Get complete manga details.

        This property combines all individual properties into a single
        MangaDetails object for convenient access to all information.

        Returns:
            MangaDetails: Complete manga information
        """
        return MangaDetails(
            url=self.manga_url,
            title=self.title,
            poster=self.poster,
            genres=self.genres,
            description=self.description,
            status=self.status,
            rate=self.rate,
            chapters=self.chapters
        )

class ChapterImagesScraper:
    """
    Scrape and download chapter images.

    This class handles extracting image URLs from a chapter page and provides
    functionality to download them and combine them into a PDF file.

    Attributes:
        url (str): URL of the chapter to scrape

    Example:
        >>> scraper = ChapterImagesScraper("https://example.com/manga/1/chapter-1")
        >>> print(f"Found {len(scraper.images)} pages")
        >>> scraper.download_images_as_pdf("chapter1.pdf")
    """

    def __init__(self, chapter_url: str):
        """
        Initialize the chapter images scraper.

        Args:
            chapter_url (str): URL of the chapter to scrape
        """
        self.url = chapter_url
        self.manga_url = "/".join(chapter_url.split("/")[:-2])

    @cached_property
    def images(self) -> List[ChapterImage]:
        """
        Get the list of images in the chapter.

        This property is cached to avoid repeated network requests.
        The images are returned in their proper reading order.

        Returns:
            List[ChapterImage]: List of chapter images with order and URL
        """
        tree = get_html(self.url)
        return [ChapterImage(order_no=i, url=node.attrs["src"].strip())
                for i, node in enumerate(tree.css("img.wp-manga-chapter-img"))]
    
    @staticmethod
    def _download_to_temp(url: str, timeout: float = 15.0) -> str:
        """
        Download an image to a temporary file.

        Args:
            url (str): URL of the image to download
            timeout (float): Request timeout in seconds

        Returns:
            str: Path to the temporary file containing the image

        Raises:
            requests.RequestException: If the download fails
        """
        session = get_session()
        resp = session.get(url, timeout=timeout, stream=True)
        resp.raise_for_status()
        suffix = Path(url).suffix or ".img"
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        with tmp as f:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        return tmp.name

    def download_images_as_pdf(self, out_path: str = "output.pdf") -> None:
        """
        Download all chapter images and combine them into a PDF file.

        This method downloads all images concurrently using a thread pool,
        then combines them into a single PDF file. The images are automatically
        cleaned up after the PDF is created.

        Args:
            out_path (str): Path where to save the PDF file

        Raises:
            Exception: If any image download fails or PDF creation fails
        """
        images_urls = [img.url for img in self.images]
        tmp_files = []
        try:
            with ThreadPoolExecutor(max_workers=6) as ex:
                futures = {ex.submit(ChapterImagesScraper._download_to_temp, url): url for url in images_urls}
                for fut in as_completed(futures):
                    url = futures[fut]
                    try:
                        tmp_files.append(fut.result())
                    except Exception:
                        logger.exception("Failed to download %s", url)
                        raise

            with open(out_path, "wb") as f_out:
                f_out.write(img2pdf.convert(tmp_files))
        finally:
            for p in tmp_files:
                try:
                    Path(p).unlink()
                except Exception:
                    logger.debug("Failed to remove temp file %s", p)

class SerieScraper:
    """
    Static class for browsing all available manga series.

    This class provides functionality to list and fetch all manga series
    available on the site. It supports pagination and parallel fetching
    for better performance, and can save manga data to the database.

    Class Attributes:
        TOTAL_RESULTS (int): Total number of manga series found
        TOTAL_PAGES (int): Total number of pages
        MAX_RESULTS_PER_PAGE (int): Maximum results shown per page
        MAX_THREADS (int): Maximum concurrent threads for fetching

    Example:
        >>> SerieScraper.save_all_manga()
        >>> all_manga = SerieScraper.start()
        >>> print(f"Found {len(all_manga)} manga series")
    """
    
    TOTAL_RESULTS = 0
    TOTAL_PAGES = 0
    MAX_RESULTS_PER_PAGE = 12
    MAX_THREADS = 5
    
    @staticmethod
    def generate_url(number: int = 1) -> str:
        """
        Generate URL for a specific page number.

        Args:
            number (int): Page number

        Returns:
            str: URL for the specified page
        """
        return f"https://azoramoon.com/series/page/{number}/"
    
    @staticmethod
    def get_total_pages() -> int:
        """
        Get the total number of pages of manga series.

        This method fetches the first page and extracts the total count
        of manga series to calculate the total number of pages.

        Returns:
            int: Total number of pages available
        """
        url: str = SerieScraper.generate_url()
        html: LexborHTMLParser = get_html(url)
        SerieScraper.TOTAL_RESULTS = int(html.css_first("div.h4").text(strip=True).split(" ")[0])
        SerieScraper.TOTAL_PAGES = SerieScraper.TOTAL_RESULTS // SerieScraper.MAX_RESULTS_PER_PAGE + 1
        return SerieScraper.TOTAL_PAGES
    
    @staticmethod
    def get_links(page_num: int) -> List[str]:
        """
        Get manga links from a specific page.

        Args:
            page_num (int): Page number to fetch

        Returns:
            List[str]: List of manga URLs from the page
        """
        url: str = SerieScraper.generate_url(number=page_num)
        html: LexborHTMLParser = get_html(url)
        links: Set[str] = {link_node.attrs["href"] for link_node in html.css("h3 a")}
        return links
    
    @staticmethod
    def start() -> Set[str]:
        """
        Start fetching manga links from multiple pages in parallel.

        This method uses a thread pool to fetch multiple pages concurrently,
        improving the speed of collecting all manga URLs. Shows progress bar.

        Returns:
            Set[str]: Set of all unique manga URLs found
        """
        total_pages = SerieScraper.get_total_pages()
        links: Set[str] = set()
        with ThreadPoolExecutor(max_workers=SerieScraper.MAX_THREADS) as ex:
            futures = [ex.submit(SerieScraper.get_links, page) for page in range(1, total_pages + 1)]
            with tqdm(total=len(futures), desc="Fetching manga links", unit="page") as pbar:
                for fut in as_completed(futures):
                    try:
                        part = fut.result()
                        links.update(part)
                    except Exception:
                        logger.exception("Error fetching page")
                    finally:
                        pbar.update(1)
        return links
    
    @staticmethod
    def _save_manga_to_db(manga_url: str) -> bool:
        """
        Scrape and save a single manga to the database.

        Args:
            manga_url (str): URL of the manga to scrape and save

        Returns:
            bool: True if saved successfully, False otherwise
        """
        session = get_db_session()
        try:
            # Check if manga URL already exists
            existing = session.query(MangaDB).filter(MangaDB.url == manga_url).first()
            if existing:
                logger.debug("Manga already exists in database: %s", manga_url)
                return False
            
            scraper = MangaDetailsScarper(manga_url)
            details = scraper.details
            
            manga_id = get_uuid()
            manga_db = MangaDB(
                id=manga_id,
                title=details.title,
                url=details.url,
                poster=details.poster,
                description=details.description,
                status=details.status,
                rate=float(details.rate) if details.rate else 0.0
            )
            session.add(manga_db)
            session.flush()
            
            for genre_name in details.genres:
                genre_db = GenreDB(id=get_uuid(), manga_id=manga_id, name=genre_name)
                session.add(genre_db)
            
            for chapter in details.chapters:
                chapter_db = ChapterDB(
                    id=get_uuid(),
                    manga_id=manga_id,
                    order_no=chapter.order_no,
                    title=chapter.title,
                    url=chapter.url
                )
                session.add(chapter_db)
            
            session.commit()
            logger.info("Saved manga to database: %s", details.title)
            return True
            
        except IntegrityError as e:
            session.rollback()
            logger.warning("Integrity error while saving manga: %s", manga_url)
            return False
        except Exception as e:
            session.rollback()
            logger.exception("Error saving manga to database: %s", manga_url)
            return False
        finally:
            close_db_session(session)
    
    @staticmethod
    def save_all_manga(max_workers: int = 3) -> None:
        """
        Fetch all manga links and save them to the database.

        This method scrapes all manga series from the website and saves them
        to the database with their details, genres, and chapters. Displays
        progress bars for both fetching and saving operations.

        Args:
            max_workers (int): Maximum number of concurrent worker threads

        Example:
            >>> SerieScraper.save_all_manga(max_workers=5)
        """
        init_db()
        logger.info("Starting manga scraping process")
        
        manga_links = SerieScraper.start()
        
        saved_count = 0
        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            futures = {ex.submit(SerieScraper._save_manga_to_db, url): url for url in manga_links}
            with tqdm(total=len(futures), desc="Saving manga to database", unit="manga") as pbar:
                for fut in as_completed(futures):
                    try:
                        if fut.result():
                            saved_count += 1
                    except Exception:
                        logger.exception("Error processing manga")
                    finally:
                        pbar.update(1)
        
        logger.info("Completed: Saved %d new manga to database", saved_count)