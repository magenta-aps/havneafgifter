from bs4 import BeautifulSoup
from django.conf import settings
from django.contrib.auth import BACKEND_SESSION_KEY
from django.test import TestCase
from django.urls import reverse

from havneafgifter.models import User


class LoginTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create(username="test")
        cls.user.set_password("test")
        cls.user.save()

    def test_login_form(self):
        self.client.get(reverse("havneafgifter:login"))
        response = self.client.post(
            reverse("havneafgifter:login"), {"username": "test", "password": "test"}
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], settings.LOGIN_REDIRECT_URL)

    def test_postlogin(self):
        session = self.client.session
        session.update(
            {
                "saml": {
                    "ava": {
                        "cpr": ["1234567890"],
                        "cvr": ["12345678"],
                        "firstname": ["Test"],
                        "lastname": ["Testersen"],
                        "email": ["test@example.com"],
                    }
                }
            }
        )
        session.save()
        response = self.client.get(reverse("havneafgifter:post_login"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/")

    def test_login_form_incorrect(self):
        self.client.get(reverse("havneafgifter:login"))
        response = self.client.post(
            reverse("havneafgifter:login"),
            {"username": "test", "password": "incorrect"},
        )
        self.assertEqual(response.status_code, 200)
        soup = BeautifulSoup(response.content, "html.parser")
        alert = soup.find(class_="alert")
        self.assertIsNotNone(alert)

    def test_logout_redirect_saml(self):
        self.client.login(username="test", password="test")
        session = self.client.session
        session.update(
            {
                BACKEND_SESSION_KEY: "project.auth_backend.Saml2Backend",
                "saml": {"cpr": "1234567890"},
            }
        )
        session.save()
        response = self.client.get(reverse("havneafgifter:logout"))
        self.assertEqual(response.headers["Location"], reverse("mitid:logout"))

    def test_logout_redirect_no_saml(self):
        self.client.login(username="test", password="test")
        response = self.client.get(reverse("havneafgifter:logout"))
        self.assertEqual(response.headers["Location"], settings.LOGOUT_REDIRECT_URL)
