import os
from dotenv import load_dotenv
import httpx
from typing import Optional
from httpx import Response
from src.core.interfaces import BookProvider
from src.core.models import Book
import src.core.utils as utils
import  logging

DEFAULT_USER_AGENT = "BookTracker/1.0 (unconfigured@example.com)"
load_dotenv()
logger = logging.getLogger(__name__)

class OpenLibraryClient(BookProvider):
    BASE_URL = "https://openlibrary.org"
    def __init__(self, client:Optional[httpx.Client]=None):
        user_agent = os.getenv("USER_AGENT", DEFAULT_USER_AGENT)

        if user_agent == DEFAULT_USER_AGENT:
            raise ValueError("User-Agent header is not configured, check your environment variables.")

        self.client = client or httpx.Client(
            base_url=self.BASE_URL,
            headers={"User-Agent": os.getenv("USER_AGENT", DEFAULT_USER_AGENT),
                     "Accept": "application/json",
            },
            follow_redirects=True,
            timeout=10.0,
        )

    def get_by_isbn(self, isbn: str) -> Optional[Book]:
        if not utils.validate_isbn(isbn):
            logger.warning("Invalid ISBN provided: %s", isbn)
            return None

        clean_isbn = utils.clean_isbn(isbn)
        url = f"/isbn/{clean_isbn}.json?default=false"
        try:
            logger.debug("Fetching book data from Open Library for URL: %s", url)
            response: Response = self.client.get(url)
            if response.status_code == 404:
                logger.error("Book not found in Open Library for ISBN: %s", clean_isbn)
                return None
            response.raise_for_status()
            data = response.json()
            return Book(
                isbn=clean_isbn,
                title=data.get("title", "Unknown title"),
                publish_date=data.get("publish_date", ""),
                authors=data.get("authors", []),
                genres=data.get("subjects", []),
            )
        except httpx.RequestError as e:
            logger.error("HTTP error  for URL %s: %s", e.status_code, e.request.url, str(e))
            return None
        except httpx.NetworkError as e:
            logger.error("Network error while requesting %s: %s", e.request.url, str(e))
            return None


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,  # Or logging.INFO depending on the granularity you need
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    logger.info("Open Library client initialized")
    client = OpenLibraryClient()

    book = client.get_by_isbn("9780044403371")
    print(book)