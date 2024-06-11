from unittest.mock import ANY, Mock, patch

from bs4 import BeautifulSoup
from django.contrib import messages
from django.contrib.auth.models import AnonymousUser, Group
from django.core.exceptions import PermissionDenied
from django.core.management import call_command
from django.forms import BaseFormSet
from django.http import (
    Http404,
    HttpResponse,
    HttpResponseNotFound,
    HttpResponseRedirect,
)
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
    HarborDuesFormUpdateView,
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


harbor_dues_form_arg_values = [
    # Test 1: user creates harbor dues form and is sent directly to receipt
    (
        ShipType.FREIGHTER,
        False,
        HarborDuesForm,
        "havneafgifter:receipt_detail_html",
    ),
    # Test 2: user creates cruise tax form with a port of call, and is sent to
    # the passenger tax form.
    (
        ShipType.CRUISE,
        False,
        CruiseTaxForm,
        "havneafgifter:passenger_tax_create",
    ),
    # Test 3: user creates cruise tax form without a port of call, and is sent
    # to the environmental tax form.
    (
        ShipType.CRUISE,
        True,
        CruiseTaxForm,
        "havneafgifter:environmental_tax_create",
    ),
]


class _PostHarborDuesFormDataMixin(HarborDuesFormMixin):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.request_factory = RequestFactory()
        cls.instance = cls.view_class()
        cls.user = User.objects.create(username="Test Testersen")

    def _post_data(
        self,
        data,
        vessel_type,
        no_port_of_call,
        view_url,
    ):
        self.client.force_login(self.shipping_agent_user)
        # Arrange: set up POST data
        data["vessel_type"] = vessel_type
        if no_port_of_call:
            data["no_port_of_call"] = "on"
            data["port_of_call"] = ""
        # Act: post data
        return self.client.post(view_url, data=data)

    def _assert_response_is_redirect(self, response, next_view_name, instance):
        self.assertIsInstance(response, HttpResponseRedirect)
        self.assertEqual(
            response.url,
            reverse(next_view_name, kwargs={"pk": instance.pk}),
        )


class TestHarborDuesFormCreateView(
    ParametrizedTestCase, _PostHarborDuesFormDataMixin, TestCase
):
    view_class = HarborDuesFormCreateView

    @parametrize(
        "vessel_type,no_port_of_call,model_class,next_view_name",
        harbor_dues_form_arg_values,
    )
    def test_creates_model_instance_depending_on_vessel_type(
        self,
        vessel_type,
        no_port_of_call,
        model_class,
        next_view_name,
    ):
        # Act
        response = self._post_data(
            self.harbor_dues_form_data_pk,
            vessel_type,
            no_port_of_call,
            reverse("havneafgifter:harbor_dues_form_create"),
        )
        # Assert
        instance = model_class.objects.latest("pk")
        self._assert_response_is_redirect(
            response,
            next_view_name,
            instance,
        )

    def test_ship_user(self):
        self.client.force_login(self.ship_user)
        response = self.client.get(reverse("havneafgifter:harbor_dues_form_create"))
        soup = BeautifulSoup(response.content, "html.parser")
        field = soup.find("input", attrs={"name": "vessel_imo"})
        self.assertEqual(field.attrs.get("value"), self.ship_user.username)


class TestHarborDuesFormUpdateView(
    ParametrizedTestCase, _PostHarborDuesFormDataMixin, TestCase
):
    view_class = HarborDuesFormUpdateView

    @parametrize(
        "vessel_type,no_port_of_call,model_class,next_view_name",
        harbor_dues_form_arg_values,
    )
    def test_updates_model_instance_depending_on_vessel_type(
        self,
        vessel_type,
        no_port_of_call,
        model_class,
        next_view_name,
    ):
        # Arrange: ensure that a cruise tax form exists with the expected PK
        if model_class is CruiseTaxForm:
            cruise_tax_form = CruiseTaxForm.objects.create(
                pk=self.harbor_dues_form.pk,
                date=self.harbor_dues_form.date,
                **self.harbor_dues_form_data,
            )
        else:
            cruise_tax_form = None
        # Act
        response = self._post_data(
            self.harbor_dues_form_data_pk,
            vessel_type,
            no_port_of_call,
            reverse(
                "havneafgifter:harbor_dues_form_update",
                kwargs={"pk": self.harbor_dues_form.pk},
            ),
        )
        # Assert
        instance = (
            cruise_tax_form if cruise_tax_form is not None else self.harbor_dues_form
        )
        self._assert_response_is_redirect(
            response,
            next_view_name,
            instance,
        )


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
        self._post_formset(
            # Update existing entry for first disembarkment site (index 0)
            {"number_of_passengers": 42},
            # Add new entry for next disembarkment site (index 1)
            {"number_of_passengers": 42},
        )

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


class TestReceiptDetailView(ParametrizedTestCase, HarborDuesFormMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.request_factory = RequestFactory()
        cls.view = ReceiptDetailView()
        cls.user, _ = User.objects.get_or_create(username="admin", is_superuser=True)

    def test_get_object_returns_harbor_dues_form(self):
        self.view.setup(self._request(self.user), pk=self.harbor_dues_form.pk)
        self.assertEqual(self.view.get_object(), self.harbor_dues_form)

    def test_get_object_returns_cruise_tax_form(self):
        self.view.setup(self._request(self.user), pk=self.cruise_tax_form.pk)
        self.assertEqual(self.view.get_object(), self.cruise_tax_form)

    def test_get_object_returns_none(self):
        with self.assertRaises(Http404):
            self.view.setup(self._request(self.user), pk=-1)
        self.assertIsNone(self.view.get_object())

    def test_setup_raises_permission_denied(self):
        with self.assertRaises(PermissionDenied):
            self.view.setup(self._request(AnonymousUser()), pk=self.harbor_dues_form.pk)

    def test_get_returns_html(self):
        request = self._request(self.user)
        self.view.setup(request, pk=self.harbor_dues_form.pk)
        response = self.view.get(request)
        self.assertEqual(response.status_code, HttpResponse.status_code)
        self.assertEqual(response["Content-Type"], "text/html; charset=utf-8")

    def test_post_sends_email(self):
        # Arrange
        request = self._request(self.user, method="post")
        self.view.setup(request, pk=self.harbor_dues_form.pk)
        with patch.object(self.view, "_send_email") as mock_send_email:
            # Act
            self.view.post(request)
            # Assert: verify that we call the `_send_email` method as expected
            mock_send_email.assert_called_once_with(
                self.view.get_object(),
                request,
            )

    def _request(self, user, method="get"):
        request = self.request_factory.request(method=method)
        request.user = user
        return request


class TestPreviewPDFView(HarborDuesFormMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.request_factory = RequestFactory()
        cls.view = PreviewPDFView()
        cls.user, _ = User.objects.get_or_create(username="admin", is_superuser=True)

    def test_get_returns_pdf(self):
        for obj in (self.harbor_dues_form, self.cruise_tax_form):
            with self.subTest(obj=obj):
                self.view.setup(self._request(), pk=obj.pk)
                response = self.view.get(self._request())
                self.assertEqual(response.status_code, HttpResponse.status_code)
                self.assertEqual(response["Content-Type"], "application/pdf")

    def test_get_raises_404(self):
        with self.assertRaises(Http404):
            self.view.setup(self._request(), pk=-1)
            response = self.view.get(self._request())
            self.assertIsInstance(response, HttpResponseNotFound)

    def _request(self):
        request = self.request_factory.get("")
        request.user = self.user
        return request


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
