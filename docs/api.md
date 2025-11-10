# API Documentation

This document provides detailed documentation for the Manga Scraping API classes and functions.

## Network Utilities

### `get_session(retries: int = 3, backoff_factor: float = 0.3, status_forcelist=(500, 502, 504)) -> requests.Session`

Creates or returns a cached requests Session with retry capabilities.

**Parameters:**
- `retries`: Number of retries for failed requests (default: 3)
- `backoff_factor`: Factor to calculate delay between retries (default: 0.3)
- `status_forcelist`: HTTP status codes that trigger a retry (default: (500, 502, 504))

**Returns:**
- A requests.Session object configured with retry capabilities

### `get_content(url: str, params: dict | None = None, timeout: float = 10.0) -> bytes`

Fetches raw content from a URL.

**Parameters:**
- `url`: URL to fetch content from
- `params`: Optional query parameters (default: None)
- `timeout`: Request timeout in seconds (default: 10.0)

**Returns:**
- Raw bytes content from the URL

### `get_html(url: str, params: dict | None = None, timeout: float = 10.0) -> LexborHTMLParser`

Fetches and parses HTML content from a URL.

**Parameters:**
- `url`: URL to fetch HTML from
- `params`: Optional query parameters (default: None)
- `timeout`: Request timeout in seconds (default: 10.0)

**Returns:**
- Parsed HTML document as LexborHTMLParser object

## Search Functionality

### Class `SearchResultsScraper`

A class for searching manga titles and handling search results.

#### Attributes:
- `MAX_RESULTS_PER_PAGE`: Maximum number of results per page (12)
- `search`: Search query string
- `result_no`: Total number of results found
- `pages`: Number of result pages
- `result_nodes`: Raw HTML nodes containing results
- `results`: List of parsed MangaSearchResult objects

#### Methods:

##### `__init__(self, search: str)`
Initializes the search scraper with a search query.

##### `post_result_nodes(self)`
Fetches and stores raw HTML nodes containing search results.

##### `get_result(self, result_node: LexborNode) -> MangaSearchResult`
Parses a single search result node into a MangaSearchResult object.

##### `post_results(self)`
Parses all result nodes into MangaSearchResult objects.

##### `prepare_results(self)`
Main method to fetch and prepare all search results.

## Manga Details

### Class `MangaDetailsScarper`

A class for scraping detailed information about a manga.

#### Attributes:
- `manga_url`: URL of the manga to scrape

#### Methods:

##### `__init__(self, manga_url: str)`
Initializes the scraper with a manga URL.

##### Properties:
- `title`: Get the manga title
- `poster`: Get the manga cover image URL
- `description`: Get the manga description
- `genres`: Get the list of manga genres
- `status`: Get the manga publication status
- `rate`: Get the manga rating
- `chapters`: Get the list of manga chapters
- `details`: Get complete manga details as MangaDetails object

## Chapter Images

### Class `ChapterImagesScraper`

A class for scraping and downloading chapter images.

#### Attributes:
- `url`: URL of the chapter to scrape

#### Methods:

##### `__init__(self, chapter_url: str)`
Initializes the scraper with a chapter URL.

##### `@cached_property images(self) -> List[ChapterImage]`
Gets the list of images in the chapter.

##### `_download_to_temp(url: str, timeout: float = 15.0) -> str`
Downloads an image to a temporary file.

##### `download_images_as_pdf(self, out_path: str = "output.pdf") -> None`
Downloads all chapter images and combines them into a PDF.

## Series Browsing

### Class `SerieScraper`

A static class for browsing all available manga series.

#### Class Attributes:
- `TOTAL_RESULTS`: Total number of manga series
- `TOTAL_PAGES`: Total number of pages
- `MAX_RESULTS_PER_PAGE`: Maximum results per page (12)
- `MAX_THREADS`: Maximum concurrent threads for fetching (5)

#### Methods:

##### `@staticmethod generate_url(number: int = 1) -> str`
Generates URL for a specific page number.

##### `@staticmethod get_total_pages() -> int`
Gets the total number of pages of manga series.

##### `@staticmethod get_links(page_num: int) -> List[str]`
Gets manga links from a specific page.

##### `@staticmethod start(pages_to_fetch: int) -> Set[str]`
Starts fetching manga links from multiple pages in parallel.

## Models

The API uses several data models (defined in models.py):

### `MangaSearchResult`
- `url`: Manga URL
- `title`: Manga title
- `poster`: Cover image URL
- `genres`: List of genres
- `status`: Publication status
- `rate`: Rating
- `latest_chapter`: ChapterLatest object

### `MangaDetails`
- `url`: Manga URL
- `title`: Manga title
- `poster`: Cover image URL
- `genres`: List of genres
- `description`: Manga description
- `status`: Publication status
- `rate`: Rating
- `chapters`: List of ChapterDetailed objects

### `ChapterLatest`
- `url`: Chapter URL
- `title`: Chapter title

### `ChapterDetailed`
- `order_no`: Chapter number
- `url`: Chapter URL
- `title`: Chapter title

### `ChapterImage`
- `order_no`: Image number
- `url`: Image URL

## Error Handling

The API includes several error handling mechanisms:

1. **Network Retries**: Automatically retries failed requests with exponential backoff
2. **Exception Logging**: Uses Python's logging module to log errors and debugging information
3. **Resource Cleanup**: Ensures temporary files are cleaned up after PDF creation
4. **Status Code Handling**: Retries on specific HTTP status codes (500, 502, 504)
5. **Timeout Management**: Configurable timeouts for all network requests

## Usage Examples

```python
# Search for manga
search = SearchResultsScraper("one piece")
search.prepare_results()
for result in search.results:
    print(f"Title: {result.title}")

# Get manga details
manga = MangaDetailsScarper("https://example.com/manga/title")
details = manga.details
print(f"Title: {details.title}")
print(f"Genres: {', '.join(details.genres)}")

# Download chapter as PDF
chapter = ChapterImagesScraper("https://example.com/manga/title/chapter-1")
chapter.download_images_as_pdf("chapter1.pdf")

# Browse all series
total_pages = SerieScraper.get_total_pages()
all_manga = SerieScraper.start(total_pages)
print(f"Found {len(all_manga)} manga series")
```