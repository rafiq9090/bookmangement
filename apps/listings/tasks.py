import io
import os
from celery import shared_task
from django.core.files.base import ContentFile
from PIL import Image
from apps.listings.models import ListingImage


@shared_task
def process_listing_image_to_webp(image_id: int) -> str:
    """
    Optimizes user-uploaded book inspection photos into compressed WebP format
    to minimize mobile bandwidth consumption.
    """
    try:
        listing_image = ListingImage.objects.get(id=image_id)
    except ListingImage.DoesNotExist:
        return f"ListingImage #{image_id} not found."

    if not listing_image.image:
        return "No image payload found."

    with Image.open(listing_image.image.path) as img:
        img_rgb = img.convert("RGB")
        output = io.BytesIO()
        img_rgb.save(output, format="WEBP", quality=85, optimize=True)
        output.seek(0)

        base_name = os.path.splitext(os.path.basename(listing_image.image.name))[0]
        webp_filename = f"{base_name}.webp"
        listing_image.webp_image.save(webp_filename, ContentFile(output.read()), save=True)

    return f"Image #{image_id} successfully converted to WebP."
