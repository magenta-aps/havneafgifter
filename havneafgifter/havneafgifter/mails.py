import logging
from dataclasses import dataclass
from io import BytesIO

from django.conf import settings
from django.core.files import File
from django.core.mail import EmailMessage
from django.db.models import Model
from django.templatetags.l10n import localize
from django.utils import translation
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _

from havneafgifter.models import CruiseTaxForm, HarborDuesForm, ShipType

logger = logging.getLogger(__name__)


@dataclass
class MailRecipient:
    name: str
    email: str
    object: Model | None


class NotificationMail:
    def __init__(self, form: HarborDuesForm | CruiseTaxForm):
        self.form: HarborDuesForm | CruiseTaxForm = form
        self.recipients: list[MailRecipient] = []

    def add_recipient(self, recipient: MailRecipient | None) -> None:
        if recipient is not None:
            self.recipients.append(recipient)
        return None

    def get_port_authority_recipient(self) -> MailRecipient | None:
        if (
            self.form.port_of_call
            and self.form.port_of_call.portauthority
            and self.form.port_of_call.portauthority.email
        ):
            return MailRecipient(
                name=self.form.port_of_call.portauthority.name,
                email=self.form.port_of_call.portauthority.email,
                object=self.form.port_of_call.portauthority,
            )
        elif (
            isinstance(self.form, CruiseTaxForm)
            and not self.form.has_port_of_call
            and settings.EMAIL_ADDRESS_AUTHORITY_NO_PORT_OF_CALL
        ):
            return MailRecipient(
                name=gettext("Authority for vessels without port of call"),
                email=settings.EMAIL_ADDRESS_AUTHORITY_NO_PORT_OF_CALL,
                object=None,
            )
        else:
            logger.info(
                "%r is not linked to a port authority, excluding from "
                "mail recipients",
                self,
            )
            return None

    def get_shipping_agent_recipient(self) -> MailRecipient | None:
        if self.form.shipping_agent and self.form.shipping_agent.email:
            return MailRecipient(
                name=self.form.shipping_agent.name,
                email=self.form.shipping_agent.email,
                object=self.form.shipping_agent,
            )
        else:
            logger.info(
                "%r is not linked to a shipping agent, excluding from mail recipients",
                self,
            )
            return None

    def get_tax_authority_recipient(self) -> MailRecipient | None:
        if settings.EMAIL_ADDRESS_SKATTESTYRELSEN:
            return MailRecipient(
                name=gettext("Tax Authority"),
                email=settings.EMAIL_ADDRESS_SKATTESTYRELSEN,
                object=None,
            )
        else:
            logger.info(
                "Skattestyrelsen email not configured, excluding from mail recipients",
            )
            return None

    def send_email(self) -> tuple[EmailMessage, int]:
        logger.info("Sending email %r to %r", self.mail_subject, self.mail_recipients)
        msg = EmailMessage(
            self.mail_subject,
            self.mail_body,
            from_email=settings.EMAIL_SENDER,
            bcc=self.mail_recipients,
        )
        receipt = self.form.get_receipt()
        msg.attach(
            filename=self.form.get_pdf_filename(),
            content=receipt.pdf,
            mimetype="application/pdf",
        )
        result = msg.send(fail_silently=False)
        if result:
            self.form.pdf = File(
                BytesIO(receipt.pdf), name=self.form.get_pdf_filename()
            )
            self.form.save(update_fields=["pdf"])
        return msg, result

    @property
    def mail_recipients(self) -> list[str]:
        return [recipient.email for recipient in self.recipients]

    @property
    def mail_subject(self):
        return f"Talippoq: {self.form.pk:05} ({self.form.date})"

    @property
    def mail_body(self):
        raise NotImplementedError("must be implemented by subclass")  # pragma: no cover


class OnSubmitForReviewMail(NotificationMail):
    def __init__(self, form: HarborDuesForm | CruiseTaxForm):
        super().__init__(form)
        self.add_recipient(self.get_port_authority_recipient())
        self.add_recipient(self.get_shipping_agent_recipient())
        self.add_recipient(self.get_tax_authority_recipient())

    @property
    def mail_body(self):
        # The mail body consists of the same text repeated in English, Greenlandic, and
        # Danish.
        # The text varies depending on whether the form concerns a cruise ship, or any
        # other type of vessel.
        result = []
        for lang_code, lang_name in settings.LANGUAGES:
            with translation.override(lang_code):
                context = {
                    "date": localize(self.form.date),
                    "agent": (
                        self.form.shipping_agent.name
                        if self.form.shipping_agent
                        else ""
                    ),
                }
                if self.form.vessel_type == ShipType.CRUISE:
                    text = (
                        _(
                            "%(agent)s has %(date)s reported port taxes, cruise "
                            "passenger taxes, as well as environmental and "
                            "maintenance fees in relation to a ship's call "
                            "at a Greenlandic port. See further details in the "
                            "attached overview."
                        )
                        % context
                    )
                else:
                    text = (
                        _(
                            "%(agent)s has %(date)s reported port taxes due to a "
                            "ship's call at a Greenlandic port. See further details "
                            "in the attached overview."
                        )
                        % context
                    )
                result.append(text)
        return "\n\n".join(result)
