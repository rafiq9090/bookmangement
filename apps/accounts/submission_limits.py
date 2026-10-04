"""Shared-cache limits; session rotation does not reset anonymous IP quotas."""
from hashlib import sha256
from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse


def limit_submission(request, scope, limit=5, seconds=3600):
    ip = request.META.get('REMOTE_ADDR', 'unknown')
    if getattr(settings, 'TRUST_PROXY_CLIENT_IP', False):
        ip = request.META.get('HTTP_X_FORWARDED_FOR', ip).split(',')[-1].strip()
    identities = ['ip:' + ip]
    if request.user.is_authenticated:
        identities.append('user:' + str(request.user.pk))
    try:
        for identity in identities:
            key = 'submission:' + scope + ':' + sha256(identity.encode()).hexdigest()
            count = 1 if cache.add(key, 1, seconds) else cache.incr(key)
            if count > limit:
                response = JsonResponse({'error': 'Too many submissions. Please try again later.'}, status=429)
                response['Retry-After'] = str(seconds)
                return response
    except Exception:
        return JsonResponse({'error': 'Submissions are temporarily unavailable. Please try again later.'}, status=503)
    return None
