"""Settings for the dummy communication provider ("Pigeon").

A deliberately separate service from the recruiter app: own project, own DB,
and it talks to the main app only over HTTP (REST in, signed webhooks out).
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name, default=False):
    return os.getenv(name, str(default)).lower() in ("1", "true", "yes")


SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-insecure-provider-key")
DEBUG = env_bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = os.getenv("DJANGO_ALLOWED_HOSTS", "*").split(",")

INSTALLED_APPS = ["gateway"]
MIDDLEWARE = ["django.middleware.common.CommonMiddleware"]
ROOT_URLCONF = "provider_project.urls"
WSGI_APPLICATION = "provider_project.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.getenv("PROVIDER_DB_PATH", BASE_DIR / "provider.sqlite3"),
        "OPTIONS": {"timeout": 20},
    }
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
USE_TZ = True
TIME_ZONE = "UTC"

# --- Provider behaviour -----------------------------------------------------
API_KEY = os.getenv("PROVIDER_API_KEY", "dev-provider-key")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "http://localhost:8000/api/webhooks/provider/")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "dev-webhook-secret")
# Seconds between lifecycle events (sent -> delivered -> read).
EVENT_DELAY_SECONDS = float(os.getenv("EVENT_DELAY_SECONDS", "2"))
WEBHOOK_MAX_ATTEMPTS = int(os.getenv("WEBHOOK_MAX_ATTEMPTS", "3"))
WEBHOOK_RETRY_DELAY = float(os.getenv("WEBHOOK_RETRY_DELAY", "1"))
# Fire lifecycle events from a background thread. Tests turn this off.
WEBHOOK_THREADED = env_bool("WEBHOOK_THREADED", True)
