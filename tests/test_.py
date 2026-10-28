"""Tests for OpenLibraryClient using httpx mock transports.

Following the project's guiding principles (simplicity first, minimal dependencies),
these tests use httpx's built-in MockTransport to simulate HTTP interactions with the
Open Library API without making actual network requests or requiring external mocking suites.
"""

from typing import List
import httpx
import pytest

from src.core.models import Book
from src.infrastructure.open_library import (
    COVER_SIZE,
    COVERS_URL,
    DEFAULT_USER_AGENT,
    OpenLibraryClient,
)

VALID_ISBN13 = "9780044403371"
FORMATTED_ISBN13 = "978-0-04-440337-1"
VALID_ISBN10 = "0441172717"
INVALID_ISBN = "1234567890"  # Invalid checksum
TEST_USER_AGENT = "BookTrackerTests/1.0 (test@example.com)"


@pytest.fixture(autouse=True)
def set_valid_user_agent(monkeypatch):
    """Ensure a valid User-Agent is set in the environment by default for tests."""
    monkeypatch.setenv("USER_AGENT", TEST_USER_AGENT)


def build_mock_client(handler) -> httpx.Client:
    """Helper to create an httpx.Client configured with MockTransport and base_url."""
    return httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url=OpenLibraryClient.BASE_URL,
    )


# ============================================================================
# 1. Initialization and Configuration Tests
# ============================================================================


def test_init_raises_error_when_user_agent_unconfigured(monkeypatch):
    """OpenLibraryClient must fail to initialize if USER_AGENT is not configured."""
    monkeypatch.delenv("USER_AGENT", raising=False)
    with pytest.raises(ValueError, match="User-Agent header is not configured"):
        OpenLibraryClient()


def test_init_raises_error_when_user_agent_is_default(monkeypatch):
    """OpenLibraryClient must fail to initialize if USER_AGENT equals DEFAULT_USER_AGENT."""
    monkeypatch.setenv("USER_AGENT", DEFAULT_USER_AGENT)
    with pytest.raises(ValueError, match="User-Agent header is not configured"):
        OpenLibraryClient()


def test_init_succeeds_with_configured_user_agent():
    """OpenLibraryClient initializes properly when a valid USER_AGENT is provided."""
    client = OpenLibraryClient()
    assert client.client.headers["user-agent"] == TEST_USER_AGENT


def test_init_uses_injected_client():
    """OpenLibraryClient should use the custom httpx.Client passed into the constructor."""
    custom_client = httpx.Client(base_url=OpenLibraryClient.BASE_URL)
    ol_client = OpenLibraryClient(client=custom_client)
    assert ol_client.client is custom_client


# ============================================================================
# 2. ISBN Pre-Validation Tests
# ============================================================================


def test_get_by_isbn_invalid_isbn_returns_none_without_network_call():
    """An invalid ISBN must return None immediately without making an HTTP request."""
    request_made = False

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal request_made
        request_made = True
        return httpx.Response(200, json={})

    client = OpenLibraryClient(client=build_mock_client(handler))
    result = client.get_by_isbn(INVALID_ISBN)

    assert result is None
    assert not request_made


# ============================================================================
# 3. Successful Book Lookup Tests
# ============================================================================


def test_get_by_isbn_success_full_data():
    """Successful retrieval with full metadata (title, author, subjects, cover)."""
    requested_urls: List[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_urls.append(str(request.url))
        if request.url.path == f"/isbn/{VALID_ISBN13}.json":
            return httpx.Response(
                200,
                json={
                    "title": "The Fellowship of the Ring",
                    "publish_date": "1954",
                    "authors": [{"key": "/authors/OL26320A"}],
                    "subjects": ["Fantasy", "Adventure"],
                    "covers": [12345],
                },
            )
        if request.url.path == "/authors/OL26320A.json":
            return httpx.Response(200, json={"name": "J. R. R. Tolkien"})
        return httpx.Response(404)

    client = OpenLibraryClient(client=build_mock_client(handler))
    book = client.get_by_isbn(VALID_ISBN13)

    assert isinstance(book, Book)
    assert book.isbn == VALID_ISBN13
    assert book.title == "The Fellowship of the Ring"
    assert book.publish_date == "1954"
    assert book.authors == ["J. R. R. Tolkien"]
    assert book.genres == ["Fantasy", "Adventure"]
    assert book.cover_url == f"{COVERS_URL}/12345-{COVER_SIZE}.jpg"
    assert len(requested_urls) == 2


def test_get_by_isbn_cleans_formatted_isbn():
    """Hyphenated or spaced ISBNs are cleaned before dispatching the request."""
    captured_paths: List[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_paths.append(request.url.path)
        if request.url.path == f"/isbn/{VALID_ISBN13}.json":
            return httpx.Response(200, json={"title": "Test Book", "authors": []})
        return httpx.Response(404)

    client = OpenLibraryClient(client=build_mock_client(handler))
    book = client.get_by_isbn(FORMATTED_ISBN13)

    assert book is not None
    assert book.isbn == VALID_ISBN13
    assert captured_paths == [f"/isbn/{VALID_ISBN13}.json"]


def test_get_by_isbn_success_isbn10():
    """Supports valid 10-digit ISBNs."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == f"/isbn/{VALID_ISBN10}.json":
            return httpx.Response(200, json={"title": "Dune", "authors": []})
        return httpx.Response(404)

    client = OpenLibraryClient(client=build_mock_client(handler))
    book = client.get_by_isbn(VALID_ISBN10)

    assert book is not None
    assert book.isbn == VALID_ISBN10
    assert book.title == "Dune"


# ============================================================================
# 4. Cover ID Handling Tests
# ============================================================================


def test_get_by_isbn_ignores_negative_one_cover_id():
    """Open Library uses -1 to designate 'no cover'; the first positive ID must be chosen."""

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "title": "Cover Test",
                "covers": [-1, 998877],
                "authors": [],
            },
        )

    client = OpenLibraryClient(client=build_mock_client(handler))
    book = client.get_by_isbn(VALID_ISBN13)

    assert book is not None
    assert book.cover_url == f"{COVERS_URL}/998877-{COVER_SIZE}.jpg"


def test_get_by_isbn_no_positive_covers_yields_none():
    """When covers list is empty or contains only -1, cover_url must be None."""

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"title": "No Cover", "covers": [-1], "authors": []},
        )

    client = OpenLibraryClient(client=build_mock_client(handler))
    book = client.get_by_isbn(VALID_ISBN13)

    assert book is not None
    assert book.cover_url is None


def test_get_by_isbn_missing_covers_key_yields_none():
    """When 'covers' key is absent from response, cover_url must be None."""

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"title": "No Covers Key", "authors": []})

    client = OpenLibraryClient(client=build_mock_client(handler))
    book = client.get_by_isbn(VALID_ISBN13)

    assert book is not None
    assert book.cover_url is None


# ============================================================================
# 5. Author Name Resolution Tests
# ============================================================================


def test_author_name_successful_resolution():
    """_author_name fetches and returns author name from author key endpoint."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/authors/OL12345A.json":
            return httpx.Response(200, json={"name": "George Orwell"})
        return httpx.Response(404)

    client = OpenLibraryClient(client=build_mock_client(handler))
    author_name = client._author_name("/authors/OL12345A")

    assert author_name == "George Orwell"


def test_author_name_http_error_returns_none():
    """_author_name returns None and does not raise when lookup returns HTTP error."""

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="Internal Server Error")

    client = OpenLibraryClient(client=build_mock_client(handler))
    author_name = client._author_name("/authors/OL12345A")

    assert author_name is None


def test_author_name_invalid_json_returns_none():
    """_author_name returns None when the response body is not valid JSON."""

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"invalid json")

    client = OpenLibraryClient(client=build_mock_client(handler))
    author_name = client._author_name("/authors/OL12345A")

    assert author_name is None


def test_get_by_isbn_multiple_authors_resolved():
    """Multiple authors are all resolved into the authors list."""
    author_names = {
        "/authors/OL1A.json": "Neil Gaiman",
        "/authors/OL2A.json": "Terry Pratchett",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == f"/isbn/{VALID_ISBN13}.json":
            return httpx.Response(
                200,
                json={
                    "title": "Good Omens",
                    "authors": [{"key": "/authors/OL1A"}, {"key": "/authors/OL2A"}],
                },
            )
        if request.url.path in author_names:
            return httpx.Response(200, json={"name": author_names[request.url.path]})
        return httpx.Response(404)

    client = OpenLibraryClient(client=build_mock_client(handler))
    book = client.get_by_isbn(VALID_ISBN13)

    assert book is not None
    assert book.authors == ["Neil Gaiman", "Terry Pratchett"]


def test_get_by_isbn_failed_author_lookup_is_skipped():
    """If one author lookup fails, other resolved authors are retained without crashing."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == f"/isbn/{VALID_ISBN13}.json":
            return httpx.Response(
                200,
                json={
                    "title": "Co-authored Book",
                    "authors": [{"key": "/authors/OL1A"}, {"key": "/authors/OL_FAIL"}],
                },
            )
        if request.url.path == "/authors/OL1A.json":
            return httpx.Response(200, json={"name": "Known Author"})
        if request.url.path == "/authors/OL_FAIL.json":
            return httpx.Response(404)
        return httpx.Response(404)

    client = OpenLibraryClient(client=build_mock_client(handler))
    book = client.get_by_isbn(VALID_ISBN13)

    assert book is not None
    assert book.authors == ["Known Author"]


def test_get_by_isbn_missing_title_defaults_to_unknown():
    """When title is not present in response, it defaults to 'Unknown title'."""

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"authors": []})

    client = OpenLibraryClient(client=build_mock_client(handler))
    book = client.get_by_isbn(VALID_ISBN13)

    assert book is not None
    assert book.title == "Unknown title"


# ============================================================================
# 6. HTTP Error Handling in get_by_isbn
# ============================================================================


def test_get_by_isbn_not_found_404_returns_none():
    """HTTP 404 from Open Library returns None."""

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": "notfound"})

    client = OpenLibraryClient(client=build_mock_client(handler))
    book = client.get_by_isbn(VALID_ISBN13)

    assert book is None


def test_get_by_isbn_server_error_500_returns_none():
    """HTTP 500 server error returns None without uncaught exception."""

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="Internal Server Error")

    client = OpenLibraryClient(client=build_mock_client(handler))
    book = client.get_by_isbn(VALID_ISBN13)

    assert book is None


def test_get_by_isbn_connection_error_returns_none():
    """httpx.ConnectError is caught and results in None."""

    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Network unreachable")

    client = OpenLibraryClient(client=build_mock_client(handler))
    book = client.get_by_isbn(VALID_ISBN13)

    assert book is None


def test_get_by_isbn_timeout_returns_none():
    """httpx.TimeoutException is caught and results in None."""

    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("Connection timed out")

    client = OpenLibraryClient(client=build_mock_client(handler))
    book = client.get_by_isbn(VALID_ISBN13)

    assert book is None


def test_get_by_isbn_malformed_json_returns_none():
    """Invalid JSON response returns None gracefully."""

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"<html>Internal Error</html>")

    client = OpenLibraryClient(client=build_mock_client(handler))
    book = client.get_by_isbn(VALID_ISBN13)

    assert book is None
