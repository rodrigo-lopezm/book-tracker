from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class Book:
    isbn: str
    title: str
    authors: List[str] = field(default_factory=list)
    genres: Optional[List[str]] = field(default_factory=list)
    publish_date: Optional[str] = None
    work_id: Optional[str] = None
    cover_url: Optional[str] = None
    literary_form: Optional[str] = None