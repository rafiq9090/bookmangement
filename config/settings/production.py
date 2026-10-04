from .base import *

DEBUG = False

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

from django.core.exceptions import ImproperlyConfigured
if not os.environ.get("SECRET_KEY"):
    raise ImproperlyConfigured("SECRET_KEY is required in production.")
if "*" in ALLOWED_HOSTS:
    raise ImproperlyConfigured("Configure explicit ALLOWED_HOSTS in production.")

if len(SECRET_KEY) < 50 or SECRET_KEY.startswith("django-insecure-"):
    raise ImproperlyConfigured("Provide a strong unique production SECRET_KEY (at least 50 characters).")
if not ALLOWED_HOSTS:
    raise ImproperlyConfigured("Configure at least one production host.")
CSRF_TRUSTED_ORIGINS = [origin.strip() for origin in os.environ.get("CSRF_TRUSTED_ORIGINS", "").split(",") if origin.strip()]
CACHES = {"default": {"BACKEND": "django.core.cache.backends.redis.RedisCache", "LOCATION": REDIS_URL, "OPTIONS": {"socket_connect_timeout": 2, "socket_timeout": 2}}}
if GEOCODING_ENABLED and not GEOCODING_USER_AGENT:
    raise ImproperlyConfigured("Set an identifying GEOCODING_USER_AGENT before enabling external geocoding.")
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
LOGGING = {"version": 1, "disable_existing_loggers": False, "handlers": {"console": {"class": "logging.StreamHandler"}}, "root": {"handlers": ["console"], "level": "INFO"}}

# Enable only behind the included private Caddy/Gunicorn network.
TRUST_PROXY_CLIENT_IP = os.environ.get("TRUST_PROXY_CLIENT_IP", "False").lower() == "true"
