import json
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from .services.recommendations import coordinates, KEY


@require_POST
def recommendation_preferences(request):
    try:
        data = json.loads(request.body)
        if data.get("reset_interests"):
            request.session.pop(KEY, None)
        if data.get("clear_location"):
            request.session.pop("recommendation_location", None)
        if "lat" in data or "lon" in data:
            coords = coordinates(data.get("lat"), data.get("lon"))
            if coords is None:
                return JsonResponse({"error": "Invalid location."}, status=400)
            # Approximate coordinates are sufficient for nearby ranking.
            request.session["recommendation_location"] = [round(value, 2) for value in coords]
        return JsonResponse({"ok": True})
    except (ValueError, TypeError, AttributeError):
        return JsonResponse({"error": "Invalid preferences."}, status=400)
