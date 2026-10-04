from django.contrib.postgres.operations import TrigramExtension
from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [('books', '0003_alter_book_isbn_13')]
    operations = [TrigramExtension()]
