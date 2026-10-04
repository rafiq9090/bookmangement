import base64
import json
from urllib.parse import urlsplit
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_GET, require_POST
from pathlib import Path
from .models import PushSubscription


def push_enabled():
    return bool(settings.WEB_PUSH_PUBLIC_KEY and settings.WEB_PUSH_PRIVATE_KEY and settings.WEB_PUSH_SUBJECT)


@require_GET
def service_worker(request):
    response = HttpResponse((Path(settings.BASE_DIR) / "static/js/push-worker.js").read_text(encoding="utf-8"), content_type="application/javascript")
    response["Cache-Control"] = "no-cache"
    response["Service-Worker-Allowed"] = "/"
    return response


@login_required
@require_GET
def push_config(request):
    return JsonResponse({"enabled": push_enabled(), "publicKey": settings.WEB_PUSH_PUBLIC_KEY})


@login_required
@require_POST
def push_subscription(request):
    try:
        data = json.loads(request.body)
        endpoint = data["endpoint"]
        parsed = urlsplit(endpoint)
        allowed = any(parsed.hostname == host or parsed.hostname.endswith("." + host) for host in settings.WEB_PUSH_ALLOWED_HOSTS)
        if len(endpoint) > 2048 or parsed.scheme != "https" or parsed.port not in (None, 443) or parsed.username or parsed.password or not allowed:
            raise ValueError()
        if data.get("unsubscribe"):
            PushSubscription.objects.filter(user=request.user, endpoint=endpoint).delete()
            return JsonResponse({"ok": True})
        if not push_enabled():
            return JsonResponse({"error": "Push notifications are not configured yet."}, status=503)
        keys = data["keys"]
        for name, size in (("p256dh", 65), ("auth", 16)):
            value = keys[name]
            if not isinstance(value, str) or len(value) > 100 or len(base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))) != size:
                raise ValueError()
        # A browser subscription belongs to the currently signed-in account.
        PushSubscription.objects.update_or_create(endpoint=endpoint, defaults={"user": request.user, "keys": {key: keys[key] for key in ("p256dh", "auth")}})
        request.session["push_endpoint"] = endpoint
        return JsonResponse({"ok": True})
    except (ValueError, KeyError, TypeError, AttributeError):
        return JsonResponse({"error": "Invalid push subscription."}, status=400)
