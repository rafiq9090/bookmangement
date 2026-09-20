from decimal import Decimal
from django.core.management.base import BaseCommand
from apps.accounts.models import CustomUser
from apps.books.models import Author, Book, Category
from apps.listings.models import BookListing


class Command(BaseCommand):
    help = "Seeds initial categories, authors, books, and listings matching the storefront design."

    def handle(self, *args, **options):
        self.stdout.write("Seeding books catalog...")

        # 1. Create or get default seller
        seller, _ = CustomUser.objects.get_or_create(
            email="seller@edoxbookshop.com",
            defaults={
                "first_name": "Official",
                "last_name": "Store",
                "is_seller": True,
            },
        )
        if not seller.has_usable_password():
            seller.set_password("SellerPass123!")
            seller.save()

        # 2. Categories
        categories_data = [
            ("Non Fiction", "non-fiction", "Biographies, science, essays, and factual knowledge."),
            ("Fiction", "fiction", "Novels, stories, literature, and imagination."),
            ("History", "history", "Historical events, revolutions, biographies of leaders."),
            ("Thriller", "thriller", "Suspense, mystery, psychological thrillers, crime."),
            ("Poetry", "poetry", "Classic and contemporary verses, rhymes, and poems."),
            ("Science", "science", "Astrophysics, biology, nature, and tech innovations."),
            ("Design & Art", "design-art", "UI/UX, graphic design, architecture, and paintings."),
            ("Psychology", "psychology", "Human behavior, cognitive thinking, and emotional growth."),
        ]
        cat_map = {}
        for name, slug, desc in categories_data:
            cat, _ = Category.objects.get_or_create(
                slug=slug,
                defaults={"name": name, "description": desc},
            )
            cat_map[slug] = cat

        # 3. Authors
        author1, _ = Author.objects.get_or_create(
            slug="vanessa-howell",
            defaults={"name": "Vanessa Howell", "biography": "Bestselling designer, writer, and illustrator."},
        )
        author2, _ = Author.objects.get_or_create(
            slug="ronald-richards",
            defaults={"name": "Ronald Richards", "biography": "Acclaimed historian, crime novelist, and essayist."},
        )

        # 4. Books and Listings
        books_data = [
            {
                "title": "Learn Abstract Design",
                "isbn_13": "9781002365478",
                "isbn_10": "1002365478",
                "author": author1,
                "category": cat_map["design-art"],
                "publisher": "Creative Press",
                "year": 2022,
                "price": Decimal("3.36"),
                "mrp": Decimal("6.50"),
                "condition": BookListing.Condition.LIKE_NEW,
                "card_style": "abstract",
                "notes": "Crisp white pages, minimal edge wear.",
            },
            {
                "title": "The Winter Stories",
                "isbn_13": "9782002365479",
                "isbn_10": "2002365479",
                "author": author1,
                "category": cat_map["fiction"],
                "publisher": "Nordic Tales Publishing",
                "year": 2021,
                "price": Decimal("4.50"),
                "mrp": Decimal("8.00"),
                "condition": BookListing.Condition.VERY_GOOD,
                "card_style": "winter",
                "notes": "Clean spine, no pen markings.",
            },
            {
                "title": "Little Green Tales: Forest of Crocodile",
                "isbn_13": "9783002365480",
                "isbn_10": "3002365480",
                "author": author2,
                "category": cat_map["non-fiction"],
                "publisher": "Emerald Nature Books",
                "year": 2020,
                "price": Decimal("5.20"),
                "mrp": Decimal("10.00"),
                "condition": BookListing.Condition.GOOD,
                "card_style": "green",
                "notes": "Slight corner softening on front cover.",
            },
            {
                "title": "The Birds: Day in the Forest",
                "isbn_13": "9784002365481",
                "isbn_10": "4002365481",
                "author": author2,
                "category": cat_map["poetry"],
                "publisher": "Avian Library",
                "year": 2023,
                "price": Decimal("3.80"),
                "mrp": Decimal("7.00"),
                "condition": BookListing.Condition.LIKE_NEW,
                "card_style": "birds",
                "notes": "Like new condition, gift quality.",
            },
            {
                "title": "Black Night: Dark Fiction",
                "isbn_13": "9785002365482",
                "isbn_10": "5002365482",
                "author": author2,
                "category": cat_map["thriller"],
                "publisher": "Shadow Nocturne",
                "year": 2019,
                "price": Decimal("6.00"),
                "mrp": Decimal("12.00"),
                "condition": BookListing.Condition.COLLECTIBLE,
                "card_style": "night",
                "notes": "First edition hardcover, rare dust jacket included.",
            },
            {
                "title": "The Big Book of Science",
                "isbn_13": "9786002365483",
                "isbn_10": "6002365483",
                "author": author2,
                "category": cat_map["science"],
                "publisher": "Cosmos Discovery",
                "year": 2021,
                "price": Decimal("4.20"),
                "mrp": Decimal("9.00"),
                "condition": BookListing.Condition.LIKE_NEW,
                "card_style": "science",
                "notes": "Full color plates intact, pristine binding.",
            },
            {
                "title": "Murdering Last Year: Crime Mystery",
                "isbn_13": "9787002365484",
                "isbn_10": "7002365484",
                "author": author2,
                "category": cat_map["thriller"],
                "publisher": "London Detective House",
                "year": 2018,
                "price": Decimal("3.90"),
                "mrp": Decimal("8.50"),
                "condition": BookListing.Condition.GOOD,
                "card_style": "mystery",
                "notes": "Light shelf wear, solid binding.",
            },
            {
                "title": "Everything You Never Knew",
                "isbn_13": "9788002365485",
                "isbn_10": "8002365485",
                "author": author1,
                "category": cat_map["psychology"],
                "publisher": "Mind Horizon",
                "year": 2022,
                "price": Decimal("5.50"),
                "mrp": Decimal("11.00"),
                "condition": BookListing.Condition.VERY_GOOD,
                "card_style": "psychology",
                "notes": "Clean pages, great reader copy.",
            },
            {
                "title": "Glittering Stars: Vol. 1",
                "isbn_13": "9789002365486",
                "isbn_10": "9002365486",
                "author": author1,
                "category": cat_map["fiction"],
                "publisher": "Celestial Arts",
                "year": 2020,
                "price": Decimal("4.80"),
                "mrp": Decimal("9.50"),
                "condition": BookListing.Condition.COLLECTIBLE,
                "card_style": "stars",
                "notes": "Signed by Vanessa Howell with golden embossment.",
            },
            {
                "title": "Night Castle: Royal Chronicles",
                "isbn_13": "9781102365487",
                "isbn_10": "1102365487",
                "author": author2,
                "category": cat_map["history"],
                "publisher": "Heritage Chronicles",
                "year": 2017,
                "price": Decimal("3.50"),
                "mrp": Decimal("7.50"),
                "condition": BookListing.Condition.LIKE_NEW,
                "card_style": "castle",
                "notes": "Rare illustrated edition.",
            },
            {
                "title": "London Crimes & Riddles: 18th Century",
                "isbn_13": "9781202365488",
                "isbn_10": "1202365488",
                "author": author2,
                "category": cat_map["history"],
                "publisher": "Old Fleet Press",
                "year": 2016,
                "price": Decimal("7.00"),
                "mrp": Decimal("14.00"),
                "condition": BookListing.Condition.COLLECTIBLE,
                "card_style": "london",
                "notes": "Vintage leather-like binding, pristine condition.",
            },
            {
                "title": "The Creative Spark: Unleash Thought",
                "isbn_13": "9781302365489",
                "isbn_10": "1302365489",
                "author": author1,
                "category": cat_map["design-art"],
                "publisher": "Modern Design Guild",
                "year": 2023,
                "price": Decimal("4.99"),
                "mrp": Decimal("9.99"),
                "condition": BookListing.Condition.VERY_GOOD,
                "card_style": "spark",
                "notes": "Softcover edition, clean margins.",
            },
        ]

        created_count = 0
        for item in books_data:
            book, b_created = Book.objects.get_or_create(
                isbn_13=item["isbn_13"],
                defaults={
                    "title": item["title"],
                    "isbn_10": item["isbn_10"],
                    "publisher": item["publisher"],
                    "publication_year": item["year"],
                    "description": f"Starting off in an eighteenth century London, this book invites readers to an exciting journey. {item['title']} explores deep narratives and vivid concepts.",
                },
            )
            book.authors.add(item["author"])
            book.categories.add(item["category"])

            listing, l_created = BookListing.objects.get_or_create(
                book=book,
                seller=seller,
                defaults={
                    "price": item["price"],
                    "original_mrp": item["mrp"],
                    "condition": item["condition"],
                    "condition_notes": item["notes"],
                    "edition_year": item["year"],
                    "status": BookListing.Status.ACTIVE,
                },
            )
            if l_created or b_created:
                created_count += 1

        self.stdout.write(self.style.SUCCESS(f"Successfully seeded {created_count} books & listings!"))
