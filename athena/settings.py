"""
Django settings for Athena prediction platform.
"""
import os
from pathlib import Path

from common.utils.env_util import load_env

# Build paths
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment (layered: .env, .env.dev/.env.test/.env.prod)
env = load_env(BASE_DIR)

# Security
SECRET_KEY = env("SECRET_KEY", default="django-insecure-athena-dev-key-change-in-production")
DEBUG = env.bool("DEBUG", default=True)

# Hosts
allowed_hosts_raw = os.environ.get("ALLOWED_HOSTS") or env("ALLOWED_HOSTS", default="localhost,127.0.0.1")
ALLOWED_HOSTS = ["*"] if allowed_hosts_raw == "*" else [h.strip() for h in str(allowed_hosts_raw).split(",") if h.strip()]

# Application definition
INSTALLED_APPS = [
    "app_console",
    "app_frontend",
    "platform_app",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "athena.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "app_console" / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "app_console.context_processors.console_context",
            ],
        },
    },
]

WSGI_APPLICATION = "athena.wsgi.application"

# Database (MySQL)
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": env("DB_NAME", default="athena"),
        "USER": env("DB_USER", default="root"),
        "PASSWORD": env("DB_PASSWORD", default=""),
        "HOST": env("DB_HOST", default="127.0.0.1"),
        "PORT": env("DB_PORT", default="3306"),
        "OPTIONS": {"charset": "utf8mb4", "connect_timeout": 5},
        "TEST": {"NAME": env("DB_TEST_NAME", default="athena_test")},
    }
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Internationalization
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# Static files
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# Default primary key
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Resource root for artifacts, data files (default: resources under project root)
RESOURCE_ROOT = env("RESOURCE_ROOT", default="resources")
if RESOURCE_ROOT and not os.path.isabs(RESOURCE_ROOT):
    RESOURCE_ROOT = str(BASE_DIR / RESOURCE_ROOT)

# Snowflake ID service (optional, for run_id generation)
# e.g. SNOWFLAKE_ID_URL=http://localhost:18041/api/snowflake/id?bid=1002
SNOWFLAKE_ID_URL = os.environ.get("SNOWFLAKE_ID_URL", "")

# CORS
CORS_ALLOW_ALL_ORIGINS = True

# Logging
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {"format": "[{levelname}] {message}", "style": "{"},
    },
    "handlers": {
        "console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "athena": {"level": "INFO"},
        "platform": {"level": "INFO"},
    },
}
