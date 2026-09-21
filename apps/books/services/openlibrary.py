from typing import Any
import requests
from django.core.files.base import ContentFile
from django.db.models import Q
from apps.books.models import Author, Book, Category


def fetch_or_create_book_by_isbn(isbn: str) -> Book | None:
    """
    Looks up ISBN in local DB first; if absent, enriches metadata from OpenLibrary API.
    """
    clean_isbn = isbn.replace("-", "").strip()
    existing_book = Book.objects.filter(Q(isbn_13=clean_isbn) | Q(isbn_10=clean_isbn)).first()
    if existing_book:
        return existing_book

    url = f"https://openlibrary.org/isbn/{clean_isbn}.json"
    headers = {"User-Agent": "eBookshopApp/1.0 (catalog lookup)"}

    try:
        response = requests.get(url, headers=headers, timeout=6)
        if response.status_code != 200:
            return None
        book_data: dict[str, Any] = response.json()
    except requests.RequestException:
        return None

    if not book_data or not book_data.get("title"):
        return None

    title = book_data.get("title")
    publishers = book_data.get("publishers", [])
    publisher = publishers[0] if publishers and isinstance(publishers[0], str) else ""
    publish_date = book_data.get("publish_date", "")

    pub_year = None
    for token in str(publish_date).split():
        if token.isdigit() and len(token) == 4:
            pub_year = int(token)
            break

    # Extract ISBN-13 and ISBN-10
    isbn_13_list = book_data.get("isbn_13", [])
    isbn_10_list = book_data.get("isbn_10", [])
    isbn_13 = isbn_13_list[0] if isbn_13_list else (clean_isbn if len(clean_isbn) == 13 else "")
    isbn_10 = isbn_10_list[0] if isbn_10_list else (clean_isbn if len(clean_isbn) == 10 else "")

    book = Book.objects.create(
        title=title,
        isbn_13=isbn_13,
        isbn_10=isbn_10,
        publisher=publisher,
        publication_year=pub_year,
        description=f"Published by {publisher} ({publish_date})" if publisher else "",
    )

    # Resolve author
    authors_list = book_data.get("authors", [])
    if authors_list:
        auth_ref = authors_list[0].get("key")
        if auth_ref:
            try:
                auth_res = requests.get(f"https://openlibrary.org{auth_ref}.json", headers=headers, timeout=4)
                if auth_res.status_code == 200:
                    auth_name = auth_res.json().get("name", "").strip()
                    if auth_name:
                        author, _ = Author.objects.get_or_create(name=auth_name)
                        book.authors.add(author)
            except requests.RequestException:
                pass

    # Attach default category if available
    default_cat = Category.objects.filter(slug="fiction").first() or Category.objects.first()
    if default_cat:
        book.categories.add(default_cat)

    # Download cover image if available
    covers = book_data.get("covers", [])
    if covers and covers[0] > 0:
        cover_id = covers[0]
        cover_url = f"https://covers.openlibrary.org/b/id/{cover_id}-L.jpg"
        try:
            img_res = requests.get(cover_url, headers=headers, timeout=5)
            if img_res.status_code == 200 and len(img_res.content) > 1000:
                book.cover_image.save(f"{clean_isbn}.jpg", ContentFile(img_res.content), save=True)
        except requests.RequestException:
            pass

    return book
