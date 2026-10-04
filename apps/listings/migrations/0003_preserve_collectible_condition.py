from django.db import migrations


def preserve_collectibles(apps, schema_editor):
    Listing = apps.get_model('listings', 'BookListing')
    Listing.objects.filter(condition='COLLECTIBLE').update(is_collectible=True, condition_needs_review=True)
    # Keep the original condition value until the owner explicitly regrades it.
    # Discovery/request services hide copies requiring review.

class Migration(migrations.Migration):
    dependencies = [('listings', '0002_booklisting_area_booklisting_condition_needs_review_and_more')]
    operations = [migrations.RunPython(preserve_collectibles, migrations.RunPython.noop)]
