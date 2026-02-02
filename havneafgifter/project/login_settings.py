import os

from django.urls import reverse_lazy
from project.util import strtobool

DEBUG = bool(strtobool(os.environ.get("DJANGO_DEBUG", "False")))

SESSION_COOKIE_SECURE = not DEBUG
if not DEBUG:
    SESSION_COOKIE_SAMESITE = "None"
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

LOGIN_REDIRECT_URL = reverse_lazy("havneafgifter:post_login")
LOGIN_URL = reverse_lazy("havneafgifter:login")
LOGOUT_REDIRECT_URL = reverse_lazy("havneafgifter:logged_out")
