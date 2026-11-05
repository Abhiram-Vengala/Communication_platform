import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name, default=False):
    return os.getenv(name, str(default)).lower() in ("1", "true", "yes")


SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-insecure-key-change-me")
DEBUG = env_bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = os.getenv("DJANGO_ALLOWED_HOSTS", "*").split(",")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "candidates",
    "messaging",
]
MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]
ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    }
]
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.getenv("DB_PATH", BASE_DIR / "db.sqlite3"),
        # The web process and the worker share this file; wait instead of erroring.
        "OPTIONS": {"timeout": 20},
    }
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
USE_TZ = True
TIME_ZONE = "UTC"
STATIC_URL = "static/"

CORS_ALLOWED_ORIGINS = os.getenv(
    "CORS_ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:3000"
).split(",")

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PAGINATION_CLASS": "config.pagination.DefaultPagination",
    "EXCEPTION_HANDLER": "config.exceptions.api_exception_handler",
}

# --- Messaging --------------------------------------------------------------
# Each entry is a "communication method" the recruiter can pick. Both are served
# by the dummy provider service, which is a separate project in /provider.
_PROVIDER_URL = os.getenv("PROVIDER_BASE_URL", "http://localhost:8001")
PROVIDERS = {
    "whatsapp": {"label": "WhatsApp", "channel": "whatsapp", "base_url": _PROVIDER_URL},
    "email": {"label": "Email", "channel": "email", "base_url": _PROVIDER_URL},
}
DEFAULT_PROVIDER = "whatsapp"
PROVIDER_API_KEY = os.getenv("PROVIDER_API_KEY", "dev-provider-key")
PROVIDER_TIMEOUT_SECONDS = float(os.getenv("PROVIDER_TIMEOUT_SECONDS", "5"))
PROVIDER_WEBHOOK_SECRET = os.getenv("PROVIDER_WEBHOOK_SECRET", "dev-webhook-secret")

MESSAGE_MAX_ATTEMPTS = int(os.getenv("MESSAGE_MAX_ATTEMPTS", "4"))
# Delay before attempt 2, 3, ... (seconds). The last value repeats.
MESSAGE_RETRY_BACKOFF = [5, 30, 120]
MESSAGE_RETRY_AFTER_CAP = 300
# A message stuck in "sending" (worker crashed) is requeued after this long.
MESSAGE_STUCK_AFTER_SECONDS = 120
# Send inline in the request instead of via the worker (handy for quick demos/tests).
MESSAGING_EAGER_DISPATCH = env_bool("MESSAGING_EAGER_DISPATCH", False)
MAX_BULK_RECIPIENTS = 500
