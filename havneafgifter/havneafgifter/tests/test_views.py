from unittest.mock import ANY, Mock, patch

from bs4 import BeautifulSoup
from django.contrib import messages
from django.contrib.auth.models import AnonymousUser, Group
from django.core.exceptions import PermissionDenied
from django.core.management import call_command
from django.forms import BaseFormSet
from django.http import HttpResponseNotFound, HttpResponseRedirect
from django.test import RequestFactory, TestCase
from django.urls import reverse
from unittest_parametrize import ParametrizedTestCase, parametrize

from havneafgifter.models import (
    CruiseTaxForm,
    Disembarkment,
    DisembarkmentSite,
    HarborDuesForm,
    Nationality,
    PassengersByCountry,
    PortAuthority,
    ShippingAgent,
    ShipType,
    User,
)
from havneafgifter.tests.mixins import HarborDuesFormMixin
from havneafgifter.views import (
    EnvironmentalTaxCreateView,
    HarborDuesFormCreateView,
    HarborDuesFormListView,
    PassengerTaxCreateView,
    PreviewPDFView,
    ReceiptDetailView,
    _CruiseTaxFormSetView,
    _SendEmailMixin,
)


class TestRootView(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        call_command("create_groups", verbosity=1)

    def test_redirect(self):
        response = self.client.get(reverse("havneafgifter:root"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], reverse("havneafgifter:login"))

    def test_redirect_ship(self):
        user = User.objects.create(username="Boaty McBoatface")
        user.groups.add(Group.objects.get(name="Ship"))
        self.client.force_login(user)
        response = self.client.get(reverse("havneafgifter:root"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.headers["Location"],
            reverse("havneafgifter:harbor_dues_form_create"),
        )

    def test_redirect_shipping(self):
        user = User.objects.create(username="Sortskæg")
        user.groups.add(Group.objects.get(name="Shipping"))
        self.client.force_login(user)
        response = self.client.get(reverse("havneafgifter:root"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.headers["Location"],
            reverse("havneafgifter:harbor_dues_form_create"),
        )

    def test_saml(self):
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
        response = self.client.get(reverse("havneafgifter:root"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.headers["Location"],
            reverse("havneafgifter:harbor_dues_form_create"),
        )


class TestPostLoginView(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        call_command("create_groups", verbosity=1)

    def test_redirect_not_logged_in(self):
        response = self.client.get(reverse("havneafgifter:post_login"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.headers["Location"], reverse("havneafgifter:login-failed")
        )

    def test_redirect_logged_in_agent(self):
        user = User.objects.create(username="JamesBond")
        user.groups.add(Group.objects.get(name="Shipping"))
        self.client.force_login(user)
        response = self.client.get(reverse("havneafgifter:post_login"))
        self.assertEqual(response.status_code, 302)
        # Update this when default landing page changes
        # in PostLoginView.get_redirect_url
        self.assertEqual(
            response.headers["Location"],
            reverse("havneafgifter:root"),
        )

    def test_redirect_logged_in_ship(self):
        user = User.objects.create(username="9074729")
        user.groups.add(Group.objects.get(name="Ship"))
        self.client.force_login(user)
        response = self.client.get(reverse("havneafgifter:post_login"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.headers["Location"],
            reverse("havneafgifter:root"),
        )


class TestSendEmailMixin(ParametrizedTestCase, HarborDuesFormMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.request_factory = RequestFactory()

    @parametrize(
        "status,expected_message_class",
        [
            (0, messages.ERROR),
            (1, messages.SUCCESS),
        ],
    )
    def test_send_email_produces_message(self, status, expected_message_class):
        instance = _SendEmailMixin()
        with patch("havneafgifter.views.messages.add_message") as mock_add_message:
            with patch(
                "havneafgifter.models.HarborDuesForm.send_email",
                return_value=(Mock(), status),
            ) as mock_send_email:
                instance._send_email(
                    self.harbor_dues_form,
                    self.request_factory.post("/"),
                )
                mock_send_email.assert_called_once_with()
                mock_add_message.assert_called_once_with(
                    ANY, expected_message_class, ANY
                )


class TestHarborDuesFormCreateView(ParametrizedTestCase, HarborDuesFormMixin, TestCase):
    view_class = HarborDuesFormCreateView

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.request_factory = RequestFactory()
        cls.instance = cls.view_class()
        cls.user = User.objects.create(username="Test Testersen")

    @parametrize(
        "vessel_type,model_class,next_view_name",
        [
            # Test 1: freighter, etc. creates harbor dues form and sends user
            # to the harbor dues form detail view.
            (
                ShipType.FREIGHTER,
                HarborDuesForm,
                "havneafgifter:receipt_detail_html",
            ),
            # Test 2: cruise ship creates cruise tax form and sends user to the
            # passenger tax form.
            (
                ShipType.CRUISE,
                CruiseTaxForm,
                "havneafgifter:passenger_tax_create",
            ),
        ],
    )
    def test_creates_model_instance_depending_on_vessel_type(
        self, vessel_type, model_class, next_view_name
    ):
        self.client.force_login(self.shipping_agent_user)
        self.harbor_dues_form_data_pk["vessel_type"] = vessel_type
        response = self.client.post(
            reverse("havneafgifter:harbor_dues_form_create"),
            data=self.harbor_dues_form_data_pk,
        )
        instance = model_class.objects.latest("pk")
        self.assertIsInstance(response, HttpResponseRedirect)
        self.assertEqual(
            response.url,
            reverse(next_view_name, kwargs={"pk": instance.pk}),
        )

    def test_ship_user(self):
        self.client.force_login(self.ship_user)
        response = self.client.get(reverse("havneafgifter:harbor_dues_form_create"))
        soup = BeautifulSoup(response.content, "html.parser")
        field = soup.find("input", attrs={"name": "vessel_imo"})
        self.assertEqual(field.attrs.get("value"), self.ship_user.username)

    def test_sends_email_and_displays_confirmation_message_on_submit(self):
        """When a form is completed (for other vessel types than cruise ships),
        the receipt must be emailed to the relevant recipients, and a confirmation
        message must be displayed to the user submitting the form.
        """
        with patch.object(self.instance, "_send_email") as mock_send_email:
            request = self._post_form(self.harbor_dues_form_data_pk)
            self.instance.post(request)
            # Assert that we call the `_send_email` method as expected
            mock_send_email.assert_called_once_with(
                HarborDuesForm.objects.latest("pk"),
                request,
            )

    def _post_form(self, data):
        request = self.request_factory.post("", data=data)
        request.user = self.user
        self.instance.request = request
        return request


class TestCruiseTaxFormSetView(HarborDuesFormMixin, TestCase):
    view_class = _CruiseTaxFormSetView

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.request_factory = RequestFactory()
        cls.get_request = cls.request_factory.get("")
        cls.instance = cls.view_class()
        cls.instance._cruise_tax_form = cls.cruise_tax_form

    def test_setup(self):
        with patch.object(CruiseTaxForm.objects, "get") as mock_get:
            self.instance.setup(self.get_request, pk=0)
            mock_get.assert_called_once_with(pk=0)

    def _assert_get_form_returns_expected_formset(self):
        self.instance.request = self.get_request
        formset = self.instance.get_form()
        self.assertIsInstance(formset, BaseFormSet)
        self.assertIs(formset.form, self.view_class.form_class)
        self.assertFalse(formset.can_order)
        self.assertFalse(formset.can_delete)
        self.assertEqual(formset.extra, 0)

    def _assert_get_context_data_includes_formset(self, name):
        self.instance.request = self.get_request
        context_data = self.instance.get_context_data()
        self.assertIsInstance(context_data[name], BaseFormSet)

    def _post_formset(self, *form_items, prefix="form", **extra):
        data = {
            "form-TOTAL_FORMS": len(form_items),
            "form-INITIAL_FORMS": len(form_items),
            **extra,
        }
        for idx, item in enumerate(form_items):
            for key, val in item.items():
                data[f"{prefix}-{idx}-{key}"] = val
        self.instance.request = self.request_factory.post("", data=data)
        return self.instance.request


class TestPassengerTaxCreateView(TestCruiseTaxFormSetView):
    view_class = PassengerTaxCreateView

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        # Create an existing `PassengersByCountry` object (which is updated during
        # the test.)
        cls._existing_passengers_by_country = PassengersByCountry.objects.create(
            cruise_tax_form=cls.cruise_tax_form,
            nationality=Nationality.BELGIUM,
            number_of_passengers=10,
        )

    def test_get_form_returns_expected_formset(self):
        self._assert_get_form_returns_expected_formset()

    def test_get_form_kwargs_populates_initial(self):
        self.instance.request = self.get_request
        form_kwargs = self.instance.get_form_kwargs()
        self.assertListEqual(
            form_kwargs["initial"],
            [
                {
                    "nationality": nationality,
                    "number_of_passengers": (
                        0
                        if nationality != Nationality.BELGIUM
                        else self._existing_passengers_by_country.number_of_passengers
                    ),
                    "pk": (
                        None
                        if nationality != Nationality.BELGIUM
                        else self._existing_passengers_by_country.pk
                    ),
                }
                for nationality in Nationality
            ],
        )

    def test_get_context_data_populates_formset(self):
        self._assert_get_context_data_includes_formset("passengers_by_country_formset")

    def test_form_valid_creates_objects(self):
        # Arrange
        request = self._post_formset(
            # Add new entry for Australia (index 0)
            {"number_of_passengers": 42},
            # Add new (empty) entry for Austria (index 1)
            {"number_of_passengers": 0},
            # Update existing entry for Belgium (index 2)
            {"number_of_passengers": 42},
            # Submit correct number of total passengers
            total_number_of_passengers=2 * 42,
        )
        # Act: trigger DB insert logic
        self.instance.post(request)
        # Assert: verify that the specified `PassengersByCountry` objects are
        # created.
        self.assertQuerySetEqual(
            self.cruise_tax_form.passengers_by_country.values(
                "cruise_tax_form",
                "nationality",
                "number_of_passengers",
            ),
            [
                {
                    "cruise_tax_form": self.cruise_tax_form.pk,
                    "nationality": Nationality.AUSTRALIA.value,
                    "number_of_passengers": 42,
                },
                {
                    "cruise_tax_form": self.cruise_tax_form.pk,
                    "nationality": Nationality.BELGIUM.value,
                    "number_of_passengers": 42,
                },
            ],
        )

    def test_total_number_of_passengers_validation(self):
        request = self._post_formset(
            {"number_of_passengers": 40},
            {"number_of_passengers": 40},
            total_number_of_passengers=100,
        )
        response = self.instance.post(request)
        context_data = response.context_data
        passengers_total_form = context_data["passengers_total_form"]
        passengers_by_country_formset = context_data["passengers_by_country_formset"]
        self.assertFalse(passengers_total_form.is_valid())
        self.assertTrue(passengers_by_country_formset.is_valid())


class TestEnvironmentalTaxCreateView(TestCruiseTaxFormSetView):
    view_class = EnvironmentalTaxCreateView

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        # Create an existing `Disembarkment` object (which is updated during the
        # test.)
        cls._disembarkment_site_1 = DisembarkmentSite.objects.first()
        cls._disembarkment_site_2 = DisembarkmentSite.objects.all()[1]
        cls._existing_disembarkment = Disembarkment.objects.create(
            cruise_tax_form=cls.cruise_tax_form,
            disembarkment_site=cls._disembarkment_site_1,
            number_of_passengers=10,
        )

    def test_get_form_returns_expected_formset(self):
        self._assert_get_form_returns_expected_formset()

    def test_get_form_kwargs_populates_initial(self):
        self.instance.request = self.get_request
        form_kwargs = self.instance.get_form_kwargs()
        self.assertListEqual(
            form_kwargs["initial"],
            [
                {
                    "disembarkment_site": ds.pk,
                    "number_of_passengers": (
                        0
                        if ds != self._existing_disembarkment.disembarkment_site
                        else self._existing_disembarkment.number_of_passengers
                    ),
                    "pk": (
                        None
                        if ds != self._existing_disembarkment.disembarkment_site
                        else self._existing_disembarkment.pk
                    ),
                }
                for ds in DisembarkmentSite.objects.all()
            ],
        )

    def test_get_context_data_populates_formset(self):
        self._assert_get_context_data_includes_formset("disembarkment_formset")

    def test_form_valid_creates_objects(self):
        # Arrange
        request = self._post_formset(
            # Update existing entry for first disembarkment site (index 0)
            {"number_of_passengers": 42},
            # Add new entry for next disembarkment site (index 1)
            {"number_of_passengers": 42},
        )
        with patch.object(self.instance, "_send_email") as mock_send_email:
            # Act: trigger DB insert logic
            self.instance.form_valid(self.instance.get_form())
            # Assert: verify that the specified `Disembarkment` objects are
            # created.
            self.assertQuerySetEqual(
                self.cruise_tax_form.disembarkment_set.values(
                    "cruise_tax_form",
                    "disembarkment_site",
                    "number_of_passengers",
                ).order_by("disembarkment_site__pk"),
                [
                    {
                        "cruise_tax_form": self.cruise_tax_form.pk,
                        "disembarkment_site": ds.pk,
                        "number_of_passengers": 42,
                    }
                    for ds in [
                        self._disembarkment_site_1,
                        self._disembarkment_site_2,
                    ]
                ],
            )
            # Assert: verify that we call the `_send_email` method as expected
            mock_send_email.assert_called_once_with(
                self.instance._cruise_tax_form,
                request,
            )


class TestReceiptDetailView(ParametrizedTestCase, HarborDuesFormMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.request_factory = RequestFactory()
        cls.view = ReceiptDetailView()
        cls.user = User.objects.create(username="admin", is_superuser=True)

    def test_get_object_returns_harbor_dues_form(self):
        self.view.kwargs = {"pk": self.harbor_dues_form.pk}
        request = self.request_factory.get("")
        request.user = self.user
        self.view.get(request)
        self.assertEqual(self.view.get_object(), self.harbor_dues_form)

    def test_get_object_returns_cruise_tax_form(self):
        self.view.kwargs = {"pk": self.cruise_tax_form.pk}
        request = self.request_factory.get("")
        request.user = self.user
        self.view.get(request)
        self.assertEqual(self.view.get_object(), self.cruise_tax_form)

    def test_get_object_return_permission_denied(self):
        self.view.kwargs = {"pk": self.harbor_dues_form.pk}
        request = self.request_factory.get("")
        request.user = AnonymousUser()
        with self.assertRaises(PermissionDenied):
            self.view.get(request)

    def test_get_object_returns_none(self):
        self.view.kwargs = {"pk": -1}
        self.view.get(self.request_factory.get(""))
        self.assertIsNone(self.view.get_object())


class TestPreviewPDFView(HarborDuesFormMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.request_factory = RequestFactory()
        cls.view = PreviewPDFView()

    def test_get_returns_pdf(self):
        for obj in (self.harbor_dues_form, self.cruise_tax_form):
            with self.subTest(obj=obj):
                self.view.kwargs = {"pk": obj.pk}
                response = self.view.get(self.request_factory.get(""))
                self.assertEqual(response["Content-Type"], "application/pdf")

    def test_get_returns_404(self):
        self.view.kwargs = {"pk": -1}
        response = self.view.get(self.request_factory.get(""))
        self.assertIsInstance(response, HttpResponseNotFound)


class TestHarborDuesFormListView(HarborDuesFormMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.request_factory = RequestFactory()
        cls.view = HarborDuesFormListView()

    def test_list_admin(self):
        request = self.request_factory.get("")
        request.user = User.objects.create(username="admin", is_superuser=True)
        self.view.setup(request)
        self.view.get(request)
        self.assertIn(self.harbor_dues_form, self.view.get_queryset())

    def test_list_agent(self):
        request = self.request_factory.get("")
        request.user = self.shipping_agent_user
        self.view.setup(request)
        self.view.get(request)
        self.assertIn(self.harbor_dues_form, self.view.get_queryset())

    def test_list_port_authority(self):
        request = self.request_factory.get("")
        request.user = self.port_authority_user
        self.view.setup(request)
        self.view.get(request)
        self.assertIn(self.harbor_dues_form, self.view.get_queryset())

    def test_list_other_agent(self):
        request = self.request_factory.get("")
        request.user = User.objects.create(
            username="other_shipping_agent",
            shipping_agent=ShippingAgent.objects.create(name="Impostor"),
        )
        request.user.groups.add(Group.objects.get(name="Shipping"))
        self.view.setup(request)
        self.view.get(request)
        self.assertNotIn(self.harbor_dues_form, self.view.get_queryset())

    def test_list_other_port_authority(self):
        request = self.request_factory.get("")
        request.user = User.objects.create(
            username="other_port_auth",
            port_authority=PortAuthority.objects.create(email="impostor@example.org"),
        )
        request.user.groups.add(Group.objects.get(name="PortAuthority"))
        self.view.setup(request)
        self.view.get(request)
        self.assertNotIn(self.harbor_dues_form, self.view.get_queryset())
