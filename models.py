from pydantic import BaseModel
from typing import List

class BaseManga(BaseModel) :
    url: str
    title: str
    poster: str
    genres: List[str]
    status: str
    rate: float


class ChapterLatest(BaseModel) :
    url: str
    title: str

class ChapterDetailed(ChapterLatest) :
    order_no: int

class MangaSearchResult(BaseManga) :
    latest_chapter: ChapterLatest

class MangaDetails(BaseManga) :
    description: str
    chapters: List[ChapterDetailed]

class ChapterImage(BaseModel) :
    order_no: int
    url: str