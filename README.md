# Manga API

A Python-based web scraping API for retrieving manga information, chapters, and images from manga websites.

## Features

- Search for manga titles
- Get detailed manga information
- List manga chapters
- Extract chapter images
- Download chapters as PDF
- Browse all available series

## Installation

1. Clone the repository:
```bash
git clone https://github.com/Hmou05/MANGA-API.git
cd MANGA-API
```

2. Create a virtual environment and activate it:
```bash
python -m venv .venv
# On Windows
.venv\Scripts\activate
# On Unix/macOS
source .venv/bin/activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### Search for Manga

```python
from scraper import SearchResultsScraper

# Create a search instance
search = SearchResultsScraper("one piece")
search.prepare_results()

# Access the results
for result in search.results:
    print(f"Title: {result.title}")
    print(f"Status: {result.status}")
    print(f"Latest Chapter: {result.latest_chapter.title}")
    print("---")
```

### Get Manga Details

```python
from scraper import MangaDetailsScarper

# Get manga details
manga = MangaDetailsScarper("https://example.com/manga/title")
details = manga.details

print(f"Title: {details.title}")
print(f"Status: {details.status}")
print(f"Rating: {details.rate}")
print(f"Genres: {', '.join(details.genres)}")
print(f"Description: {details.description}")

# List chapters
for chapter in details.chapters:
    print(f"Chapter {chapter.order_no}: {chapter.title}")
```

### Download Chapter as PDF

```python
from scraper import ChapterImagesScraper

# Download chapter as PDF
chapter = ChapterImagesScraper("https://example.com/manga/title/chapter-1")
chapter.download_images_as_pdf("chapter1.pdf")
```

### Browse All Series

```python
from scraper import SerieScraper

# Get total pages
total_pages = SerieScraper.get_total_pages()

# Get all manga links
links = SerieScraper.start(total_pages)
print(f"Found {len(links)} manga series")
```

## API Reference

### `SearchResultsScraper`
- **Purpose**: Search for manga titles
- **Methods**:
  - `prepare_results()`: Fetch and parse search results
  - Properties:
    - `result_no`: Number of results found
    - `pages`: Number of result pages
    - `results`: List of `MangaSearchResult` objects

### `MangaDetailsScarper`
- **Purpose**: Get detailed information about a manga
- **Properties**:
  - `title`: Manga title
  - `poster`: Cover image URL
  - `description`: Manga description
  - `genres`: List of genres
  - `status`: Publication status
  - `rate`: Rating
  - `chapters`: List of `ChapterDetailed` objects
  - `details`: Complete `MangaDetails` object

### `ChapterImagesScraper`
- **Purpose**: Extract and download chapter images
- **Methods**:
  - `download_images_as_pdf(out_path)`: Download chapter as PDF
- **Properties**:
  - `images`: List of `ChapterImage` objects

### `SerieScraper`
- **Purpose**: Browse all available manga series
- **Static Methods**:
  - `get_total_pages()`: Get total number of pages
  - `get_links(page_num)`: Get manga links from a specific page
  - `start(pages_to_fetch)`: Fetch manga links from multiple pages in parallel

## Data Models

### `MangaSearchResult`
- `url`: Manga URL
- `title`: Manga title
- `poster`: Cover image URL
- `genres`: List of genres
- `status`: Publication status
- `rate`: Rating
- `latest_chapter`: `ChapterLatest` object

### `MangaDetails`
- `url`: Manga URL
- `title`: Manga title
- `poster`: Cover image URL
- `genres`: List of genres
- `description`: Manga description
- `status`: Publication status
- `rate`: Rating
- `chapters`: List of `ChapterDetailed` objects

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

The API includes built-in error handling for:
- Network errors (retries with backoff)
- Invalid URLs
- Missing content
- Download failures

## Testing

Run tests using pytest:
```bash
pytest tests/ -v
```

## License

[MIT License](LICENSE)
