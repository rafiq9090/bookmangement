from django.test import TestCase
from rest_framework.test import APIClient
from apps.books.models import Author, Book, Category
from apps.books.selectors import search_books


class BooksCatalogTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.author = Author.objects.create(name="George Orwell", biography="English novelist.")
        self.category = Category.objects.create(name="Dystopian")
        self.book = Book.objects.create(
            title="Nineteen Eighty-Four",
            isbn_13="9780451524935",
            publication_year=1949,
            publisher="Secker & Warburg",
        )
        self.book.authors.add(self.author)
        self.book.categories.add(self.category)

    def test_search_by_title_selector(self):
        results = search_books(query="Nineteen")
        self.assertEqual(results.count(), 1)
        self.assertEqual(results.first().id, self.book.id)

    def test_search_by_author_selector(self):
        results = search_books(query="Orwell")
        self.assertEqual(results.count(), 1)

    def test_book_list_api(self):
        response = self.client.get("/api/v1/books/?q=1984")
        self.assertEqual(response.status_code, 200)

    def test_book_detail_api(self):
        response = self.client.get(f"/api/v1/books/{self.book.slug}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["isbn_13"], "9780451524935")
