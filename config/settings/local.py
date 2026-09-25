from .base import *

DEBUG = True

INTERNAL_IPS = [
    "127.0.0.1",
]

ALLOWED_HOSTS = ["localhost", "127.0.0.1", "testserver", "*"]

# In local development, use SQLite by default unless USE_POSTGRES=True is specified
# or USE_SQLITE=False is explicitly passed with matching PostgreSQL credentials in .env
use_postgres = os.environ.get("USE_POSTGRES", "False").lower() in ("true", "1")
if not use_postgres:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
    if "django.contrib.postgres" in INSTALLED_APPS:
        INSTALLED_APPS.remove("django.contrib.postgres")
