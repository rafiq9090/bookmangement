from typing import Any
import requests
from django.core.files.base import ContentFile
from apps.books.models import Author, Book, Category

OPEN_LIBRARY_API_URL = "https://openlibrary.org/api/books"


def fetch_or_create_book_by_isbn(isbn: str) -> Book | None:
    """
    Looks up ISBN in local DB first; if absent, enriches metadata from OpenLibrary API.
    """
    clean_isbn = isbn.replace("-", "").strip()
    existing_book = Book.objects.filter(isbn_13=clean_isbn).first()
    if existing_book:
        return existing_book

    params = {
        "bibkeys": f"ISBN:{clean_isbn}",
        "format": "json",
        "jscmd": "data",
    }
    
    try:
        response = requests.get(OPEN_LIBRARY_API_URL, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException:
        return None

    book_data: dict[str, Any] = data.get(f"ISBN:{clean_isbn}", {})
    if not book_data:
        return None

    title = book_data.get("title", f"Unknown Title ({clean_isbn})")
    publisher_list = book_data.get("publishers", [])
    publisher = publisher_list[0].get("name", "") if publisher_list else ""
    publish_date = book_data.get("publish_date", "")
    
    # Extract year if present
    pub_year = None
    for token in publish_date.split():
        if token.isdigit() and len(token) == 4:
            pub_year = int(token)
            break

    book = Book.objects.create(
        title=title,
        isbn_13=clean_isbn,
        publisher=publisher,
        publication_year=pub_year,
        description=book_data.get("notes", ""),
    )

    # Attach authors
    for auth_entry in book_data.get("authors", []):
        name = auth_entry.get("name", "").strip()
        if name:
            author, _ = Author.objects.get_or_create(name=name)
            book.authors.add(author)

    # Attach subjects/genres
    for subject_entry in book_data.get("subjects", [])[:3]:
        subject_name = subject_entry.get("name", "").strip()
        if subject_name:
            cat, _ = Category.objects.get_or_create(name=subject_name)
            book.categories.add(cat)

    # Download cover image if available
    cover_urls = book_data.get("cover", {})
    large_cover = cover_urls.get("large") or cover_urls.get("medium")
    if large_cover:
        try:
            img_res = requests.get(large_cover, timeout=5)
            if img_res.status_code == 200:
                book.cover_image.save(f"{clean_isbn}.jpg", ContentFile(img_res.content), save=True)
        except requests.RequestException:
            pass

    return book
