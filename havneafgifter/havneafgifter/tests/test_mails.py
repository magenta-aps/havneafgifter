from datetime import date
from unittest.mock import patch

from django.conf import settings
from django.core.files import File
from django.test import TestCase, override_settings
from django.utils import translation
from unittest_parametrize import ParametrizedTestCase, parametrize

from havneafgifter.mails import EmailMessage, OnSubmitForReviewMail
from havneafgifter.models import HarborDuesForm, ShipType
from havneafgifter.tests.mixins import HarborDuesFormMixin


class TestOnSubmitForReviewMail(ParametrizedTestCase, HarborDuesFormMixin, TestCase):
    @override_settings(EMAIL_ADDRESS_SKATTESTYRELSEN="skattestyrelsen@example.org")
    def test_mail_recipients(self):
        instance = self._get_instance()
        self.assertListEqual(
            instance.mail_recipients,
            [
                instance.form.port_of_call.portauthority.email,
                instance.form.shipping_agent.email,
                settings.EMAIL_ADDRESS_SKATTESTYRELSEN,
            ],
        )

    @override_settings(
        EMAIL_ADDRESS_SKATTESTYRELSEN="skattestyrelsen@example.org",
        EMAIL_ADDRESS_AUTHORITY_NO_PORT_OF_CALL="ral@example.org",
    )
    def test_mail_recipients_falls_back_if_no_port_of_call(self):
        instance = OnSubmitForReviewMail(self.cruise_tax_form_without_port_of_call)
        self.assertListEqual(
            instance.mail_recipients,
            [
                settings.EMAIL_ADDRESS_AUTHORITY_NO_PORT_OF_CALL,
                instance.form.shipping_agent.email,
                settings.EMAIL_ADDRESS_SKATTESTYRELSEN,
            ],
        )

    def test_mail_recipients_excludes_missing_port_authority(self):
        def clear_port_authority(form):
            form.port_of_call.portauthority = None
            return form

        self._assert_mail_recipients_property_logs_message(
            "is not linked to a port authority, excluding from mail recipients",
            clear_port_authority,
        )

    def test_mail_recipients_excludes_missing_shipping_agent(self):
        def clear_shipping_agent(form):
            form.shipping_agent = None
            return form

        self._assert_mail_recipients_property_logs_message(
            "specified for submitter, excluding from mail recipients",
            clear_shipping_agent,
        )

    class mock_history:

        def first():
            class mock_head:
                history_user = None

                def __init__(self, history_user):
                    self.history_user = history_user

            class mock_user:
                email = "a@b.com"
                display_name = "A B"

            return mock_head(history_user=mock_user())

    @patch("havneafgifter.models.HarborDuesForm.history", new=mock_history)
    @override_settings(EMAIL_ADDRESS_SKATTESTYRELSEN="skattestyrelsen@example.org")
    def test_mail_recipients_sends_to_history_user_when_no_agent(self):
        def clear_shipping_agent(form):
            form.shipping_agent = None
            return form

        self._assert_mail_recipients_property_not_in_logs(
            "specified for submitter, excluding from mail recipients",
            clear_shipping_agent,
        )

    def test_mail_recipients_history(self):
        def clear_shipping_agent(form):
            form.shipping_agent = None
            form.save()

            return form

        self._assert_mail_recipients_property_logs_message(
            "specified for submitter, excluding from mail recipients",
            clear_shipping_agent,
        )

    @override_settings(EMAIL_ADDRESS_SKATTESTYRELSEN=None)
    def test_mail_recipients_excludes_missing_skattestyrelsen_email(self):
        self._assert_mail_recipients_property_logs_message(
            "Skattestyrelsen email not configured, excluding from mail recipients",
        )

    def test_send_email(self):
        harbor_dues_form = HarborDuesForm(**self.harbor_dues_form_data)
        harbor_dues_form.save()
        mail = OnSubmitForReviewMail(harbor_dues_form)
        with patch.object(EmailMessage, "send") as mock_send:
            # Act
            result = mail.send_email()
            # Assert the basic email fields are populated
            self.assertEqual(result.msg.subject, mail.mail_subject)
            self.assertEqual(result.msg.body, mail.mail_body)
            self.assertEqual(result.msg.bcc, mail.mail_recipients)
            self.assertEqual(result.msg.from_email, settings.EMAIL_SENDER)
            # Assert that the receipt is attached as PDF, using the correct filename
            self.assertEqual(len(result.msg.attachments), 1)
            filename, pdf_content, filetype = result.msg.attachments[0]
            self.assertTrue(filename.startswith(harbor_dues_form.form_id))
            self.assertTrue(filename.endswith(".pdf"))
            self.assertIsInstance(pdf_content, bytes)
            self.assertGreater(len(pdf_content), 0)
            self.assertEqual(filetype, "application/pdf")
            # Assert that `OnSubmitForReviewMail.send_mail` calls `EmailMessage.send` as
            # expected.
            mock_send.assert_called_once_with(fail_silently=False)
            # Assert that the generated PDF is also saved locally.
            # Refresh from DB.
            harbor_dues_form = HarborDuesForm.objects.get(pk=harbor_dues_form.pk)
            # Assert PDF file is saved on `HarborDuesForm` instance
            self.assertIsInstance(harbor_dues_form.pdf, File)
            self.assertEqual(
                harbor_dues_form.pdf.name, harbor_dues_form.get_pdf_filename()
            )

    @parametrize(
        "vessel_type,expected_text_1,expected_text_2,expected_text_3",
        [
            (
                ShipType.CRUISE,
                # English
                "Agent has Jan. 1, 2020 reported port taxes, cruise passenger taxes, "
                "as well as environmental and maintenance fees in relation to a ship's "
                "call at a Greenlandic port. See further details in the attached "
                "overview.",
                # Greenlandic
                "Umiarsuit takornariartaatit angisuut umiarsualivimmiinnerannut "
                "akitsuummik aamma avatangiisinut iluarsaassinermillu akiliummik "
                "Agent Jan. 1, 2020, umiarsuup Kalaallit Nunaanni "
                "umiarsualivimmut tulanneranut atatillugu nalunaaruteqarput. "
                "Paasissutissat ilaat ilanngussami takusinnaavatit.",
                # Danish
                "Agent har 1. januar 2020 indberettet havneafgift, "
                "krydstogtpassagerafgift samt miljø- og vedligeholdelsesgebyr i "
                "forbindelse med et skibs anløb i en grønlandsk havn. Se "
                "yderligere detaljer i vedhæftede oversigt.",
            ),
            (
                ShipType.OTHER,
                # English
                "Agent has Jan. 1, 2020 reported port taxes due to a ship's call at a "
                "Greenlandic port. See further details in the attached overview.",
                # Greenlandic
                "Agent Jan. 1, 2020 umiarsuup Kalaallit Nunaanni umiarsualivimmut "
                "tulanneranut atatillugu nalunaaruteqarput. Paasissutissat ilaat "
                "ilanngussami takusinnaavatit.",
                # Danish
                "Agent har 1. januar 2020 indberettet havneafgift i forbindelse med et "
                "skibs anløb i en grønlandsk havn. Se yderligere detaljer i vedhæftede "
                "oversigt.",
            ),
        ],
    )
    def test_mail_body(
        self, vessel_type, expected_text_1, expected_text_2, expected_text_3
    ):
        # Verify contents of mail body.
        # 1. The mail body must consist of the same text repeated in English,
        # Greenlandic, and Danish (in that order.)
        # 2. The text varies, depending on whether the vessel is a cruise ship or not.
        harbor_dues_form = HarborDuesForm(**self.harbor_dues_form_data)
        harbor_dues_form.date = date(2020, 1, 1)
        harbor_dues_form.vessel_type = vessel_type
        mail = OnSubmitForReviewMail(harbor_dues_form)
        self.assertEqual(
            mail.mail_body,
            "\n\n".join((expected_text_1, expected_text_2, expected_text_3)),
        )

    @translation.override("da")
    def test_mail_subject(self):
        # Verify contents of mail subject, and verify that mail subject is always
        # rendered in English, as we do not know the which language(s) the
        # recipient(s) can read.
        harbor_dues_form = HarborDuesForm(**self.harbor_dues_form_data)
        harbor_dues_form.date = date(2020, 1, 1)
        harbor_dues_form.save()
        mail = OnSubmitForReviewMail(harbor_dues_form)
        self.assertEqual(
            mail.mail_subject,
            f"Talippoq: {harbor_dues_form.pk:05} ({harbor_dues_form.date})",
        )

    def _get_instance(self, modifier=None):
        form = HarborDuesForm(**self.harbor_dues_form_data)
        if modifier:
            form = modifier(form)
        return OnSubmitForReviewMail(form)

    def _assert_mail_recipients_property_logs_message(self, message, modifier=None):
        with self.assertLogs() as logged:
            self._get_instance(modifier=modifier)
            self.assertTrue(
                any(record.message.endswith(message) for record in logged.records)
            )

    def _assert_mail_recipients_property_not_in_logs(self, message, modifier=None):
        with self.assertNoLogs() as logged:
            self._get_instance(modifier=modifier)
            if logged:
                self.assertFalse(
                    any(record.message.endswith(message) for record in logged.records)
                )
