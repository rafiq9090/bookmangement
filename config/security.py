"""Shared authentication and image-upload boundaries."""
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import warnings

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import JsonResponse
from django.utils.http import url_has_allowed_host_and_scheme
from PIL import Image, ImageOps, UnidentifiedImageError


def safe_next(request, fallback="/profile/"):
    value = request.GET.get("next") or request.POST.get("next") or fallback
    if url_has_allowed_host_and_scheme(value, {request.get_host()}, require_https=request.is_secure()):
        return value
    return fallback


def clean_image(upload):
    if upload.size > 10 * 1024 * 1024:
        raise ValidationError("Each image must be at most 10 MB.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            upload.seek(0)
            with Image.open(upload) as image:
                if image.format not in {"JPEG", "PNG", "WEBP"}:
                    raise ValidationError("Use a JPEG, PNG, or WebP image.")
                if image.width * image.height > 20_000_000:
                    raise ValidationError("Images must contain at most 20 million pixels.")
                image.load()
                image = ImageOps.exif_transpose(image)
                image.thumbnail((2400, 2400))
                image = image.convert("RGB")
                output = BytesIO()
                image.save(output, format="JPEG", quality=88)
        return SimpleUploadedFile(Path(upload.name).stem[:100] + ".jpg", output.getvalue(), content_type="image/jpeg")
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning, ValueError) as exc:
        raise ValidationError("Upload a valid image file.") from exc
    finally:
        upload.seek(0)


class RequestProtectionMiddleware:
    """Shared-cache IP limits and validation before web upload handlers run."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if int(request.META.get("CONTENT_LENGTH") or 0) > 60 * 1024 * 1024:
            return JsonResponse({"error": "Request exceeds the 60 MB upload limit."}, status=413)
        sensitive = request.path in {"/login/", "/register/", "/admin-login/", "/password-reset/", "/api/v1/accounts/login/", "/api/v1/accounts/register/", "/api/v1/accounts/token/refresh/"}
        if request.method == "POST" and sensitive:
            client_ip = request.META.get("REMOTE_ADDR", "unknown")
            if getattr(settings, "TRUST_PROXY_CLIENT_IP", False):
                client_ip = request.META.get("HTTP_X_FORWARDED_FOR", client_ip).split(",")[-1].strip()
            identity = sha256(client_ip.encode()).hexdigest()
            key = "auth-limit:" + identity
            try:
                if not cache.add(key, 1, 60):
                    if cache.incr(key) > settings.AUTH_REQUESTS_PER_MINUTE:
                        response = JsonResponse({"error": "Too many attempts. Try again in one minute."}, status=429)
                        response["Retry-After"] = "60"
                        return response
            except Exception:
                if not settings.DEBUG:
                    return JsonResponse({"error": "Authentication temporarily unavailable."}, status=503)
        if request.method == "POST" and request.content_type == "multipart/form-data":
            try:
                for key in ("avatar", "photos", "cover_image", "author_photo", "photo_evidence", "image"):
                    if key in request.FILES:
                        request.FILES.setlist(key, [clean_image(upload) for upload in request.FILES.getlist(key)])
            except ValidationError as exc:
                return JsonResponse({"error": " ".join(exc.messages)}, status=400)
        return self.get_response(request)
