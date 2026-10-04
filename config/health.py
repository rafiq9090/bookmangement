from django.db import connection
from django.core.cache import cache
from django.http import JsonResponse


def health(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
        cache.set('health:cache', True, timeout=30)
        if cache.get('health:cache') is not True:
            raise RuntimeError('Cache unavailable')
        return JsonResponse({'status': 'ok'})
    except Exception:
        return JsonResponse({'status': 'unavailable'}, status=503)
