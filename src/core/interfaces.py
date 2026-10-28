from abc import ABC, abstractmethod
from typing import Optional
from src.core.models import Book

class BookProvider(ABC):
    @abstractmethod
    def get_by_isbn(self, isbn: str) -> Optional[Book]:
        pass