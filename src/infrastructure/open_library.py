import logging
import os
from typing import Optional

import httpx
from dotenv import load_dotenv

import src.core.utils as utils
from src.core.interfaces import BookProvider
from src.core.models import Book

DEFAULT_USER_AGENT = "BookTracker/1.0 (unconfigured@example.com)"
COVERS_URL = "https://covers.openlibrary.org/b/id"
COVER_SIZE = "M"  # S, M or L
load_dotenv()
logger = logging.getLogger(__name__)


class OpenLibraryClient(BookProvider):
    BASE_URL = "https://openlibrary.org"

    def __init__(self, client: Optional[httpx.Client] = None):
        user_agent = os.getenv("USER_AGENT", DEFAULT_USER_AGENT)
        if user_agent == DEFAULT_USER_AGENT:
            raise ValueError("User-Agent header is not configured, check your environment variables.")

        self.client = client or httpx.Client(
            base_url=self.BASE_URL,
            headers={"User-Agent": user_agent, "Accept": "application/json"},
            follow_redirects=True,
            timeout=10.0,
        )

    def _author_name(self, author_key: str) -> Optional[str]:
        """Resolve an author key (e.g. "/authors/OL23919A") to a name; None if the lookup fails."""
        try:
            response = self.client.get(f"{author_key}.json")
            response.raise_for_status()
            return response.json().get("name")
        except (httpx.HTTPError, ValueError) as e:
            logger.warning("Author lookup failed for %s: %s", author_key, e)
            return None

    def get_by_isbn(self, isbn: str) -> Optional[Book]:
        if not utils.validate_isbn(isbn):
            logger.warning("Invalid ISBN provided: %s", isbn)
            return None

        clean_isbn = utils.clean_isbn(isbn)
        url = f"/isbn/{clean_isbn}.json?default=false"
        try:
            logger.debug("Fetching book data from Open Library for URL: %s", url)
            response = self.client.get(url)
            if response.status_code == 404:
                logger.error("Book not found in Open Library for ISBN: %s", clean_isbn)
                return None
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPError, ValueError) as e:
            logger.error("Request failed for URL %s: %s", url, e)
            return None

        names = (self._author_name(a["key"]) for a in data.get("authors", []))
        cover_id = next((c for c in data.get("covers", []) if c > 0), None)  # -1 means "no cover"
        return Book(
            isbn=clean_isbn,
            title=data.get("title", "Unknown title"),
            publish_date=data.get("publish_date"),
            authors=[n for n in names if n],
            genres=data.get("subjects", []),
            cover_url=f"{COVERS_URL}/{cover_id}-{COVER_SIZE}.jpg" if cover_id else None,
        )


def main() -> None:
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    client = OpenLibraryClient()
    print(client.get_by_isbn("9780044403371"))


if __name__ == "__main__":
    main()
