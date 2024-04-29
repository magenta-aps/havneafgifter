from django.conf import settings
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

    def test_logout_redirect_saml(self):
        self.client.login(username="test", password="test")
        self.client.cookies.load({settings.SAML_SESSION_COOKIE_NAME: "some saml data"})
        response = self.client.get(reverse("havneafgifter:logout"))
        self.assertEqual(response.headers["Location"], reverse("saml2_logout"))

    def test_logout_redirect_no_saml(self):
        self.client.login(username="test", password="test")
        response = self.client.get(reverse("havneafgifter:logout"))
        self.assertEqual(response.headers["Location"], settings.LOGOUT_REDIRECT_URL)
