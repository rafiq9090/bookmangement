from django.test import TestCase
from apps.accounts.models import CustomUser
from apps.listings.models import BookListing
from .models import Book, Author


class SearchSuggestionTests(TestCase):
    def setUp(self):
        seller = CustomUser.objects.create_user(email='suggest@example.com', password='TestPassword123!')
        self.author = Author.objects.create(name='Nazrul Islam')
        self.book = Book.objects.create(title='Selected Poetry', isbn_13='9781234567890')
        self.book.authors.add(self.author)
        self.listing = BookListing.objects.create(book=self.book, seller=seller, price=100)

    def test_title_author_and_isbn(self):
        for query in ['Poetry', 'Nazrul', '978123']:
            response = self.client.get('/api/books/suggest/', {'q': query})
            self.assertEqual(response.status_code, 200)
            items = response.json()['suggestions']
            self.assertTrue(any(i['label'] == self.book.title for i in items))
        items = self.client.get('/api/books/suggest/', {'q': 'Nazrul'}).json()['suggestions']
        self.assertTrue(any(i['kind'] == 'Author' for i in items))

    def test_hidden_sold_and_review_listings_excluded(self):
        for changes in [{'is_deleted': True}, {'status': 'SOLD', 'is_deleted': False}, {'status': 'ACTIVE', 'condition_needs_review': True}]:
            for field, value in changes.items():
                setattr(self.listing, field, value)
            self.listing.save()
            self.assertEqual(self.client.get('/api/books/suggest/', {'q': 'Nazrul'}).json()['suggestions'], [])

    def test_short_empty_and_method(self):
        self.assertEqual(self.client.get('/api/books/suggest/', {'q': 'a'}).json()['suggestions'], [])
        self.assertEqual(self.client.get('/api/books/suggest/').json()['suggestions'], [])
        self.assertEqual(self.client.post('/api/books/suggest/').status_code, 405)
        self.assertContains(self.client.get('/store/'), 'js/book-search.js')
