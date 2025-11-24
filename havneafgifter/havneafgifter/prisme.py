import logging
from datetime import date, datetime
from typing import Dict, List, TypeVar

from dict2xml import dict2xml as dict_to_xml
from django.conf import settings
from project.util import parse_isodate
from requests import Session
from xmltodict import parse as xml_to_dict
from zeep import Client
from zeep.transports import Transport

prisme_settings = settings.PRISME
logger = logging.getLogger(__name__)


class PrismeResponse:
    pass


ResponseType = TypeVar("ResponseType", bound=PrismeResponse)


class PrismeRequest[ResponseType]:

    @property
    def method(self):
        raise NotImplementedError("Must be implemented in subclass")  # pragma: no cover

    @property
    def xml(self):
        raise NotImplementedError("Must be implemented in subclass")  # pragma: no cover

    @property
    def reply_class(self) -> type[ResponseType]:
        raise NotImplementedError("Must be implemented in subclass")  # pragma: no cover


class PrismeException(Exception):
    def __init__(self, code, text, context):
        super().__init__()
        self.code = int(code)
        self.text = text
        self.context = context

    def __str__(self):
        return f"Error in response from Prisme. Code: {self.code}, Text: {self.text}"


class PrismeSELAccountRequest(PrismeRequest["PrismeSELAccountResponse"]):
    def __init__(
        self, customer_id_number, from_date: date, to_date: date, open_closed: int = 2
    ):
        super().__init__()
        self.customer_id_number = customer_id_number
        self.from_date = from_date
        self.to_date = to_date
        self.open_closed = open_closed

    @staticmethod
    def prepare(value: str | datetime | date | None) -> str:
        if value is None:
            return ""
        if isinstance(value, datetime):
            value = f"{value:%Y-%m-%dT%H:%M:%S}"
        if isinstance(value, date):
            value = f"{value:%Y-%m-%d}"
        return str(value)

    wrap = "CustTable"

    open_closed_map = {0: "Åbne", 1: "Lukkede", 2: "Åbne og Lukkede"}

    @property
    def method(self) -> str:
        return "getAccountStatementSEL"

    @property
    def xml(self) -> str:
        return dict_to_xml(
            {
                "CustIdentificationNumber": self.prepare(self.customer_id_number),
                "FromDate": self.prepare(self.from_date),
                "ToDate": self.prepare(self.to_date),
                "CustInterestCalc": self.open_closed_map[self.open_closed],
            },
            wrap=self.wrap,
        )

    @property
    def reply_class(self) -> type["PrismeSELAccountResponse"]:
        return PrismeSELAccountResponse


class PrismeSELAccountResponseTransaction(object):
    def __init__(self, data):
        self.data = data
        self.account_number = data["AccountNum"]
        self.transaction_date = parse_isodate(data["TransDate"])
        self.accounting_date = parse_isodate(data["AccountingDate"])
        self.debitor_group_id = data["CustGroup"]
        self.debitor_group_name = data["CustGroupName"]
        self.voucher = data["Voucher"]
        self.text = data["Txt"]
        self.payment_code = data["CustPaymCode"]
        self.payment_code_name = data["CustPaymDescription"]
        amount = data["AmountCur"]
        try:
            self.amount = float(amount)
        except ValueError:
            self.amount = 0
        self.remaining_amount = data["RemainAmountCur"]
        self.due_date = data["DueDate"]
        self.closed_date = data["Closed"]
        self.last_settlement_voucher = data["LastSettleVoucher"]
        self.collection_letter_date = data["CollectionLetterDate"]
        self.collection_letter_code = data["CollectionLetterCode"]
        self.claim_type_code = data["ClaimTypeCode"]
        self.invoice_number = data["Invoice"]
        self.transaction_type = data["TransType"]
        self.rate_number = data.get("RateNmb")
        self.extern_invoice_number = data.get("ExternalInvoiceNumber")


class PrismeSELAccountResponse(PrismeResponse):
    itemclass = PrismeSELAccountResponseTransaction

    def __init__(self, request: PrismeSELAccountRequest, xml: str):
        self.request = request
        self.xml: str = xml
        self.transactions: List[PrismeSELAccountResponseTransaction] = []
        if xml is not None:
            self.data: Dict = xml_to_dict(xml)
            transactions = self.data["CustTable"]["CustTrans"]
            if type(transactions) is not list:
                transactions = [transactions]
            self.transactions = [self.itemclass(x) for x in transactions]

    def __iter__(self):
        yield from self.transactions

    def __len__(self) -> int:
        return len(self.transactions)

    def __getitem__(self, item) -> PrismeSELAccountResponseTransaction:
        return self.transactions[item]


class Prisme(object):
    _client = None

    @property
    def client(self) -> Client:
        if self._client is None:
            wsdl = prisme_settings["wsdl_file"]
            session = Session()
            if "proxy" in prisme_settings:
                socks = prisme_settings["proxy"].get("socks")
                if socks:
                    proxy = f"socks5://{socks}"
                    session.proxies = {"http": proxy, "https": proxy}

            auth_settings = prisme_settings.get("auth")
            if auth_settings:
                if "basic" in auth_settings:
                    basic_settings = auth_settings["basic"]
                    session.auth = (
                        f'{basic_settings["username"]}@{basic_settings["domain"]}',
                        basic_settings["password"],
                    )
            try:
                self._client = Client(
                    wsdl=wsdl,
                    transport=Transport(
                        session=session, timeout=3600, operation_timeout=3600
                    ),
                )
            except Exception as e:
                print("Failed connecting to prisme: %s" % str(e))
                raise e
            self._client.set_ns_prefix(
                "tns", "http://schemas.datacontract.org/2004/07/Dynamics.Ax.Application"
            )
        return self._client

    def create_request_header(
        self, method: str, area: str = "SULLISSIVIK", client_version: int = 1
    ):
        request_header_class = self.client.get_type("tns:GWSRequestHeaderDCFUJ")
        return request_header_class(
            clientVersion=client_version, area=area, method=method
        )

    def create_request_body(self, xml: str | List[str]):
        if type(xml) is not list:
            xml = [xml]
        item_class = self.client.get_type("tns:GWSRequestXMLDCFUJ")
        container_class = self.client.get_type("tns:ArrayOfGWSRequestXMLDCFUJ")
        return container_class(list([item_class(xml=x) for x in xml]))

    def get_server_version(self):
        response = self.client.service.getServerVersion(
            self.create_request_header("getServerVersion")
        )
        return {
            "version": response.serverVersion,
            "description": response.serverVersionDescription,
        }

    def process_service(
        self, request_object: PrismeRequest[ResponseType], context, cvr
    ) -> List[ResponseType]:
        try:
            request_class = self.client.get_type("tns:GWSRequestDCFUJ")
            request = request_class(
                requestHeader=self.create_request_header(request_object.method),
                xmlCollection=self.create_request_body(request_object.xml),
            )
            logger.info(
                "CVR=%s Sending to %s:\n%s"
                % (cvr, request_object.method, request_object.xml)
            )
            # reply is of type GWSReplyDCFUJ
            reply = self.client.service.processService(request)

            # reply.status is of type GWSReplyStatusDCFUJ
            if reply.status.replyCode != 0:
                raise PrismeException(
                    reply.status.replyCode, reply.status.replyText, context
                )

            outputs = []
            # reply_item is of type GWSReplyInstanceDCFUJ
            for reply_item in reply.instanceCollection.GWSReplyInstanceDCFUJ:
                if reply_item.replyCode == 0:
                    logger.info(
                        "CVR=%s Receiving from %s:\n%s"
                        % (cvr, request_object.method, reply_item.xml)
                    )
                    outputs.append(
                        request_object.reply_class(request_object, reply_item.xml)
                    )
                else:
                    raise PrismeException(
                        reply_item.replyCode, reply_item.replyText, context
                    )
            return outputs
        except Exception as e:
            logger.info(
                "CVR=%s Error in process_service for %s: %s"
                % (cvr, request_object.method, str(e))
            )
            raise e

    def get_account_data(
        self, cvr, date_from, date_to
    ) -> List[PrismeSELAccountResponse]:
        return self.process_service(
            PrismeSELAccountRequest(cvr, date_from, date_to), "account", cvr
        )
