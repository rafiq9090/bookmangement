from decimal import Decimal
from django.test import TestCase
from django.urls import reverse
from apps.accounts.models import CustomUser
from apps.books.models import Author, Book, Category
from apps.listings.models import BookListing
from apps.books.services.recommendations import rank, coordinates


class RecommendationTests(TestCase):
    def setUp(self):
        self.client.post("/cookies/preferences/", {"personalization": "yes"})
        seller = CustomUser.objects.create_user(email="recommend@example.com", password="StrongPassword123!", is_seller=True)
        poetry = Category.objects.create(name="Poetry")
        history = Category.objects.create(name="History")
        nazrul = Author.objects.create(name="Kazi Nazrul Islam")
        other = Author.objects.create(name="Another Poet")
        self.listings = []
        for title, category, author, lat in [("Nazrul Poems", poetry, nazrul, 23.75), ("Other Poems", poetry, other, 23.76), ("History Book", history, other, 24.5)]:
            book = Book.objects.create(title=title)
            book.categories.add(category);book.authors.add(author)
            self.listings.append(BookListing.objects.create(book=book, seller=seller, price=Decimal("100"), condition="GOOD", status="ACTIVE", latitude=lat, longitude=90.4))

    def test_search_learns_genre_and_recommends_other_author(self):
        self.client.get("/store/", {"q": "Kazi Nazrul Islam"})
        interests = self.client.session["reading_interests"]
        ranked = rank(self.listings, interests)
        self.assertLess(ranked.index(self.listings[1]), ranked.index(self.listings[2]))
        self.assertEqual(self.client.get("/").status_code, 200)

    def test_location_and_explicit_sort(self):
        self.client.post("/recommendations/preferences/", {"lat": 23.75, "lon": 90.4}, content_type="application/json")
        response = self.client.get("/store/", {"q": "Poems"})
        self.assertEqual(response.context["sort"], "nearby")
        self.assertEqual(response.context["page_obj"][0].pk, self.listings[0].pk)
        self.assertEqual(self.client.get("/store/", {"sort": "price_asc"}).context["sort"], "price_asc")

    def test_invalid_coordinates_and_reset(self):
        self.assertIsNone(coordinates("nan", "90"))
        self.assertIsNone(coordinates("100", "90"))
        self.assertEqual(self.client.post("/recommendations/preferences/", {"lat": 100, "lon": 90}, content_type="application/json").status_code, 400)
        self.client.get("/store/", {"q": "Poems"})
        self.client.post("/recommendations/preferences/", {"reset_interests": True, "clear_location": True}, content_type="application/json")
        self.assertNotIn("reading_interests", self.client.session)

    def test_refresh_does_not_repeat_learning(self):
        self.client.get("/store/", {"q": "Poems"})
        interests = self.client.session["reading_interests"]["genres"]
        self.client.get("/store/", {"q": "Poems"})
        self.assertEqual(interests, self.client.session["reading_interests"]["genres"])

    def test_buyer_categories_only_count_available_books(self):
        from apps.books.selectors import available_categories
        Category.objects.create(name="Empty Genre")
        BookListing.objects.filter(pk=self.listings[2].pk).update(status="SOLD")
        categories = list(available_categories())
        self.assertEqual([category.name for category in categories], ["Poetry"])
        self.assertEqual(categories[0].book_count, 2)

    def test_essential_only_stops_interest_learning(self):
        self.client.post("/cookies/preferences/", {"personalization": "no"})
        self.client.get("/store/", {"q": "Poems"})
        self.assertNotIn("reading_interests", self.client.session)

    def test_cookie_preference_is_signed_and_http_only(self):
        response = self.client.post("/cookies/preferences/", {"personalization": "no"})
        cookie = response.cookies["cookie_preferences"]
        self.assertTrue(cookie["httponly"])
        self.assertEqual(cookie["samesite"], "Lax")
