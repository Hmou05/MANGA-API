from scraper import SearchResultsScraper, MangaDetailsScarper, ChapterImagesScraper
from models import MangaSearchResult, MangaDetails, ChapterImage
from fastapi import FastAPI, HTTPException, Response, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from database import Session, Manga, Chapter, ChapterImage, init_db
import requests
from typing import List, Optional
import mimetypes
from io import BytesIO
from pydantic import BaseModel
from datetime import datetime

# Response models
class MangaResponse(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    status: Optional[str] = None
    rate: Optional[float] = None
    url: str
    has_poster: bool
    total_chapters: int
    downloaded_chapters: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class ChapterStatusResponse(BaseModel):
    chapter_id: int
    title: str
    total_images: int
    downloaded_images: int
    is_complete: bool
    progress: float

class ChapterResponse(BaseModel):
    message: str
    chapter_id: int
    total_images: int

class MangaCreateResponse(BaseModel):
    message: str
    manga_id: int

# Initialize database
init_db()

app = FastAPI(
    title= "Mangaha API",
    deprecated= False
)

app.add_middleware(
    CORSMiddleware,
    allow_methods=["*"],
    allow_origins=["*"],
    allow_credentials=True,
    allow_headers=["*"]
)

async def download_image(url: str, timeout: int = 10) -> tuple[bytes, str]:
    """Download image with timeout and return content and mime type."""
    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        content_type = response.headers.get('content-type', 'image/jpeg')
        return response.content, content_type
    except Exception as e:
        print(f"Error downloading image from {url}: {e}")
        return None, None

async def download_chapter_images(chapter_id: int):
    """Background task to download chapter images."""
    with Session() as session:
        chapter = session.query(Chapter).filter(Chapter.id == chapter_id).first()
        if not chapter:
            return
            
        for image in chapter.images:
            if not image.is_downloaded:
                content, mime_type = await download_image(image.url)
                if content and mime_type:
                    image.set_image_from_bytes(content, mime_type)
        session.commit()

@app.get("/results", response_model=List[MangaSearchResult])
def get_results(search: str):
    try:
        scraper = SearchResultsScraper(search=search)
        scraper.prepare_results()
        return scraper.results
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error searching manga: {str(e)}")

@app.get("/manga", response_model=MangaDetails)
def get_details(url: str):
    try:
        scraper = MangaDetailsScarper(manga_url=url)
        return scraper.details
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting manga details: {str(e)}")

@app.get("/chapter/images", response_model=List[ChapterImage])
def get_chapter_images(url: str):
    try:
        scraper = ChapterImagesScraper(chapter_url=url)
        return [ChapterImage(order_no=img.order_no, url=img.url) for img in scraper.images]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting chapter images: {str(e)}")

@app.post("/manga/save", response_model=MangaCreateResponse)
def save_manga(url: str):
    """Save manga and its details to database."""
    with Session() as session:
        # Check if manga already exists
        existing_manga = session.query(Manga).filter(Manga.url == url).first()
        if existing_manga:
            return {"message": "Manga already exists", "manga_id": existing_manga.id}
            
        # Scrape manga details
        scraper = MangaDetailsScarper(manga_url=url)
        details = scraper.details
        
        # Create manga object
        manga = Manga(
            url=url,
            title=details.title,
            poster_url=details.poster_url,
            description=details.description,
            status=details.status,
            rate=details.rate
        )
        
        # Download and save poster image
        if details.poster_url:
            try:
                response = requests.get(details.poster_url)
                if response.status_code == 200:
                    content_type = response.headers.get('content-type', 'image/jpeg')
                    manga.set_poster_from_bytes(response.content, content_type)
            except Exception as e:
                print(f"Error downloading poster: {e}")
        
        session.add(manga)
        session.commit()
        return {"message": "Manga saved successfully", "manga_id": manga.id}

@app.get("/manga/{manga_id}", response_model=MangaResponse)
def get_manga(manga_id: int):
    """Get manga details from database."""
    try:
        with Session() as session:
            manga = session.query(Manga).filter(Manga.id == manga_id).first()
            if not manga:
                raise HTTPException(status_code=404, detail="Manga not found")
            
            # Get chapter count
            chapter_count = len(manga.chapters)
            
            # Get downloaded chapter count
            downloaded_chapters = sum(1 for chapter in manga.chapters 
                                   if all(image.is_downloaded for image in chapter.images))
            
            return {
                "id": manga.id,
                "title": manga.title,
                "description": manga.description,
                "status": manga.status,
                "rate": manga.rate,
                "url": manga.url,
                "has_poster": bool(manga.poster_image),
                "total_chapters": chapter_count,
                "downloaded_chapters": downloaded_chapters,
                "created_at": manga.created_at,
                "updated_at": manga.updated_at
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving manga: {str(e)}")

@app.get("/manga/{manga_id}/poster")
def get_manga_poster(manga_id: int):
    """Get manga poster image."""
    with Session() as session:
        manga = session.query(Manga).filter(Manga.id == manga_id).first()
        if not manga or not manga.poster_image:
            raise HTTPException(status_code=404, detail="Poster not found")
        return Response(
            content=manga.poster_image,
            media_type=manga.poster_mime_type
        )

@app.post("/chapter/save", response_model=ChapterResponse)
async def save_chapter(manga_id: int, url: str, background_tasks: BackgroundTasks):
    """Save chapter and its images to database."""
    with Session() as session:
        manga = session.query(Manga).filter(Manga.id == manga_id).first()
        if not manga:
            raise HTTPException(status_code=404, detail="Manga not found")
            
        # Check if chapter already exists
        existing_chapter = session.query(Chapter).filter(Chapter.url == url).first()
        if existing_chapter:
            return {"message": "Chapter already exists", "chapter_id": existing_chapter.id}
            
        try:
            # Scrape chapter images
            scraper = ChapterImagesScraper(chapter_url=url)
            images = scraper.images
            
            # Create chapter
            chapter = Chapter(
                manga_id=manga_id,
                url=url,
                title=url.split('/')[-1],
                order_no=len(manga.chapters) + 1
            )
            session.add(chapter)
            session.flush()  # Get chapter ID
            
            # Create image entries
            for idx, img in enumerate(images, 1):
                chapter_image = ChapterImage(
                    chapter_id=chapter.id,
                    url=img.url,
                    order_no=idx
                )
                session.add(chapter_image)
            
            session.commit()
            
            # Start background download task
            background_tasks.add_task(download_chapter_images, chapter.id)
            
            return {
                "message": "Chapter saved successfully, images downloading in background",
                "chapter_id": chapter.id,
                "total_images": len(images)
            }
            
        except Exception as e:
            session.rollback()
            raise HTTPException(status_code=500, detail=f"Error saving chapter: {str(e)}")

@app.get("/chapter/{chapter_id}/pdf")
def get_chapter_pdf(chapter_id: int):
    """Get chapter as PDF."""
    with Session() as session:
        chapter = session.query(Chapter).filter(Chapter.id == chapter_id).first()
        if not chapter:
            raise HTTPException(status_code=404, detail="Chapter not found")
            
        pdf_data = chapter.generate_pdf()
        return Response(
            content=pdf_data,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{chapter.title}.pdf"'}
        )

@app.get("/chapter/{chapter_id}/images/{image_no}")
def get_chapter_image(chapter_id: int, image_no: int):
    """Get specific chapter image."""
    with Session() as session:
        image = session.query(ChapterImage).filter(
            ChapterImage.chapter_id == chapter_id,
            ChapterImage.order_no == image_no
        ).first()
        if not image or not image.image_data:
            raise HTTPException(status_code=404, detail="Image not found")
        return Response(
            content=image.image_data,
            media_type=image.mime_type
        )

@app.get("/chapter/{chapter_id}/status", response_model=ChapterStatusResponse)
def get_chapter_status(chapter_id: int):
    """Get chapter download status."""
    with Session() as session:
        chapter = session.query(Chapter).filter(Chapter.id == chapter_id).first()
        if not chapter:
            raise HTTPException(status_code=404, detail="Chapter not found")
            
        total_images = len(chapter.images)
        downloaded_images = sum(1 for image in chapter.images if image.is_downloaded)
        
        return {
            "chapter_id": chapter.id,
            "title": chapter.title,
            "total_images": total_images,
            "downloaded_images": downloaded_images,
            "is_complete": total_images == downloaded_images,
            "progress": (downloaded_images / total_images * 100) if total_images > 0 else 0
        }
