"""
Django settings for havneafgifter project.

Generated by 'django-admin startproject' using Django 4.2.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/4.2/ref/settings/
"""

import json
import os
import sys
from pathlib import Path

import django.conf.locale
from project.util import strtobool

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent
VERSION = os.environ["COMMIT_TAG"]
CONTACT_EMAIL = os.environ.get("CONTACT_EMAIL", "")

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = bool(strtobool(os.environ.get("DJANGO_DEBUG", "False")))
ENVIRONMENT = os.environ.get("ENVIRONMENT", "development")
TESTING = len(sys.argv) > 1 and sys.argv[1] == "test"

HOST_DOMAIN = os.environ.get("HOST_DOMAIN", "http://talippoq.aka.gl")
ALLOWED_HOSTS = json.loads(os.environ.get("ALLOWED_HOSTS", "[]"))


# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_bootstrap5",
    "django_tables2",
    "havneafgifter",
    "django_select2",
    "django_filters",
    "django_mitid_auth",
    "mitid_test",
    "csp_helpers",
    "metrics",
    "tempus_dominus",
    "simple_history",
    "django_extensions",
    "compressor",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django_mitid_auth.middleware.LoginManager",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "csp.middleware.CSPMiddleware",
    "django_session_timeout.middleware.SessionTimeoutMiddleware",
    "simple_history.middleware.HistoryRequestMiddleware",
]

AUTHENTICATION_BACKENDS = [
    "havneafgifter.permissions.HavneafgiftPermissionBackend",
    "django_mitid_auth.saml.backend.Saml2Backend",
]

ROOT_URLCONF = "project.urls"

default_loaders = [
    "django.template.loaders.filesystem.Loader",
    "django.template.loaders.app_directories.Loader",
]

cached_loaders = [("django.template.loaders.cached.Loader", default_loaders)]

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [os.path.join(BASE_DIR, "templates")],
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.template.context_processors.i18n",
                "django.contrib.messages.context_processors.messages",
            ],
            "loaders": default_loaders if DEBUG else cached_loaders,
            "libraries": {
                "csp": "csp.templatetags.csp",
            },
        },
    },
]

STORAGES = {
    "staticfiles": {
        "BACKEND": (
            "django.contrib.staticfiles.storage.StaticFilesStorage"
            if TESTING
            else "whitenoise.storage.CompressedManifestStaticFilesStorage"
        )
    },
}

WSGI_APPLICATION = "project.wsgi.application"


# Database
# https://docs.djangoproject.com/en/4.2/ref/settings/#databases

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql_psycopg2",
        "NAME": os.environ["POSTGRES_DB"],
        "USER": os.environ["POSTGRES_USER"],
        "PASSWORD": os.environ["POSTGRES_PASSWORD"],
        "HOST": os.environ["POSTGRES_HOST"],
        "TIME_ZONE": os.environ.get("DJANGO_TIMEZONE", "America/Godthab"),
    },
}

# Cache(s)
# https://docs.djangoproject.com/en/5.0/ref/settings/#std-setting-CACHES

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    },
    "select2": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "TIMEOUT": None,
    },
    "saml": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "saml_cache",
        "TIMEOUT": 7200,
    },
}

# Tell select2 which cache configuration to use:
SELECT2_CACHE_BACKEND = "select2"


# Password validation
# https://docs.djangoproject.com/en/4.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/4.2/topics/i18n/

LANGUAGE_CODE = "en-US"
LANGUAGES = [
    ("en", "English"),
    ("kl", "Kalaallisut"),
    ("da", "Dansk"),
]
EXTRA_LANG_INFO = {
    "kl": {
        "code": "kl",
        "name": "Kalaallisut",
        "name_local": "Kalaallisut",
        "bidi": False,
    },
}
# Add custom languages not provided by Django
LANG_INFO = dict(django.conf.locale.LANG_INFO, **EXTRA_LANG_INFO)
django.conf.locale.LANG_INFO = LANG_INFO

TIME_ZONE = os.environ.get("DJANGO_TIMEZONE", "America/Nuuk")
USE_I18N = True
USE_L10N = True
USE_TZ = True
THOUSAND_SEPARATOR = "."
DECIMAL_SEPARATOR = ","
FORMAT_MODULE_PATH = ["havneafgifter.formats"]


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.2/howto/static-files/

STATIC_URL = "static/"
STATIC_ROOT = "/static"

# Default primary key field type
# https://docs.djangoproject.com/en/4.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Uploaded files
MEDIA_ROOT = "/upload/"
DATA_UPLOAD_MAX_MEMORY_SIZE = 20 * 1024 * 1024

# Storage
STORAGE_ROOT = "/storage/"
STORAGE_PDF = os.path.join(STORAGE_ROOT, "pdf")

# Logging
LOGGING: dict = {
    "version": 1,
    "disable_existing_loggers": True,
    "filters": {
        "require_debug_false": {
            "()": "django.utils.log.RequireDebugFalse",
        },
    },
    "formatters": {
        "simple": {
            "format": "{levelname} {name}: {message}",
            "style": "{",
        },
    },
    "handlers": {
        "gunicorn": {
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
    },
    "root": {
        "handlers": ["gunicorn"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["gunicorn"],
            "level": "INFO",
            "propagate": False,
        },
        "fontTools": {
            "level": "ERROR",
            "propagate": False,
        },
        "weasyprint": {
            "level": "ERROR",
            "propagate": False,
        },
    },
}

log_filename = "/havneafgifter.log"
if os.path.isfile(log_filename) and ENVIRONMENT != "development":
    LOGGING["handlers"]["file"] = {
        "class": "logging.FileHandler",  # eller WatchedFileHandler
        "filename": log_filename,
        "formatter": "simple",
    }
    LOGGING["root"] = {
        "handlers": ["gunicorn", "file"],
        "level": "INFO",
    }
    LOGGING["loggers"]["django"]["handlers"].append("file")

# django-bootstrap5 configuration
BOOTSTRAP5 = {
    "css_url": "/static/bootstrap/bootstrap.min.css",
    "javascript_url": "/static/bootstrap/bootstrap.bundle.min.js",
}

# Email configuration
# Ref: https://docs.djangoproject.com/en/5.0/ref/settings/#email-backend
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.environ.get("EMAIL_HOST", None)
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", 25))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", None)
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", None)
EMAIL_USE_TLS = bool(strtobool(os.environ.get("EMAIL_USE_TLS", "False")))
EMAIL_USE_SSL = bool(strtobool(os.environ.get("EMAIL_USE_SSL", "False")))
EMAIL_SENDER = os.environ.get("EMAIL_SENDER", "noreply@nanoq.gl")
EMAIL_ADDRESS_SKATTESTYRELSEN = os.environ.get("EMAIL_ADDRESS_SKATTESTYRELSEN")
EMAIL_ADDRESS_AUTHORITY_NO_PORT_OF_CALL = os.environ.get(
    "EMAIL_ADDRESS_AUTHORITY_NO_PORT_OF_CALL"
)

# django-csp
CSP_DEFAULT_SRC = (
    "'self'",
    "localhost:8000" if DEBUG else HOST_DOMAIN,
)
CSP_SCRIPT_SRC_ATTR = (
    "'self'",
    "localhost:8000" if DEBUG else HOST_DOMAIN,
    "cdnjs.cloudflare.com",
)
CSP_STYLE_SRC_ATTR = ("'self'",)
CSP_IMG_SRC = ("'self'", "data:")

AUTH_USER_MODEL = "havneafgifter.User"

DJANGO_TABLES2_TEMPLATE = "django_tables2/bootstrap5.html"

if os.environ.get("HOST_DOMAIN", False):
    CSRF_TRUSTED_ORIGINS = [os.environ["HOST_DOMAIN"]]


TEMPUS_DOMINUS_DATETIME_FORMAT = "DD/MM/YYYY HH:mm"
TEMPUS_DOMINUS_INCLUDE_ASSETS = False

COMPRESS_PRECOMPILERS = (("text/x-scss", "django_libsass.SassCompiler"),)
COMPRESS_REBUILD_TIMEOUT = 0
COMPRESS_ENABLED = True
LIBSASS_OUTPUT_STYLE = "compressed"
STATICFILES_STORAGE = "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"
STATICFILES_FINDERS = [
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
    "compressor.finders.CompressorFinder",
]

from .login_settings import *  # noqa
