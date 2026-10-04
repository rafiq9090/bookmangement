from django.core.management.base import BaseCommand
from apps.books.models import Category


class Command(BaseCommand):
    help = "Add useful book genres without changing existing categories or books."

    def handle(self, *args, **options):
        genres = [
            ("Poetry", "poetry"), ("Biography & Memoir", "biography-memoir"),
            ("Mystery & Thriller", "mystery-thriller"), ("Romance", "romance"),
            ("Religion & Philosophy", "religion-philosophy"),
            ("Business & Economics", "business-economics"),
            ("Self-Help & Personal Development", "self-help-personal-development"),
            ("Comics & Graphic Novels", "comics-graphic-novels"),
            ("Language Learning", "language-learning"),
            ("Exam Preparation", "exam-preparation"),
        ]
        count = 0
        for name, slug in genres:
            if not Category.objects.filter(name__iexact=name).exists():
                _, created = Category.objects.get_or_create(slug=slug, defaults={"name": name})
                count += created
        self.stdout.write(f"Added {count} genres.")
