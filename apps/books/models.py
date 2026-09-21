from django.conf import settings
from django.db import models
from django.utils.text import slugify


class Author(models.Model):
    name = models.CharField(max_length=200, db_index=True)
    slug = models.SlugField(max_length=220, unique=True)
    biography = models.TextField(blank=True)
    photo = models.ImageField(upload_to="authors/", blank=True, null=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Author"
        verbose_name_plural = "Authors"

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs) -> None:
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True)
    parent = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="subcategories",
    )
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Category"
        verbose_name_plural = "Categories"

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs) -> None:
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Book(models.Model):
    """
    Global canonical master catalog record.
    Multiple sellers attach their physical used copies (BookListing) to this single record.
    """
    title = models.CharField(max_length=255, db_index=True)
    slug = models.SlugField(max_length=280, unique=True)
    isbn_10 = models.CharField(max_length=10, blank=True, db_index=True)
    isbn_13 = models.CharField(max_length=13, unique=True, db_index=True)
    authors = models.ManyToManyField(Author, related_name="books")
    categories = models.ManyToManyField(Category, related_name="books")
    publisher = models.CharField(max_length=150, blank=True)
    publication_year = models.PositiveIntegerField(null=True, blank=True)
    language = models.CharField(max_length=50, default="English")
    description = models.TextField(blank=True)
    cover_image = models.ImageField(upload_to="book_covers/", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["title"]
        verbose_name = "Book"
        verbose_name_plural = "Books"
        indexes = [
            models.Index(fields=["title", "isbn_13"]),
        ]

    def __str__(self) -> str:
        return f"{self.title} ({self.isbn_13})"

    def save(self, *args, **kwargs) -> None:
        if not self.slug:
            base_slug = slugify(self.title) or "book"
            self.slug = f"{base_slug}-{self.isbn_13}"
        super().save(*args, **kwargs)


class BookReview(models.Model):
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="reviews")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="book_reviews",
    )
    name = models.CharField(max_length=150)
    rating = models.PositiveSmallIntegerField(default=5)
    headline = models.CharField(max_length=255, blank=True)
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Book Review"
        verbose_name_plural = "Book Reviews"

    def __str__(self) -> str:
        return f"{self.book.title} - {self.rating} stars by {self.name}"
