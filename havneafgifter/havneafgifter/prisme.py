import logging
from datetime import date, datetime
from typing import Any, Dict, List, TypeVar

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

    @classmethod
    def method(cls) -> str:
        raise NotImplementedError("Must be implemented in subclass")  # pragma: no cover

    @property
    def xml(self):
        raise NotImplementedError("Must be implemented in subclass")  # pragma: no cover

    @classmethod
    def response_class(cls) -> type[ResponseType]:
        raise NotImplementedError("Must be implemented in subclass")  # pragma: no cover

    @staticmethod
    def prepare(value: str | datetime | date | None) -> str:
        if value is None:
            return ""
        if isinstance(value, datetime):
            value = f"{value:%Y-%m-%dT%H:%M:%S}"
        if isinstance(value, date):
            value = f"{value:%Y-%m-%d}"
        return str(value)


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
        self,
        customer_id_number: int | str,
        from_date: date,
        to_date: date,
        open_closed: int = 2,
    ):
        super().__init__()
        self.customer_id_number = str(customer_id_number)
        self.from_date = from_date
        self.to_date = to_date
        self.open_closed = open_closed

    wrap = "CustTable"

    open_closed_map = {0: "Åbne", 1: "Lukkede", 2: "Åbne og Lukkede"}

    @classmethod
    def method(cls) -> str:
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

    @classmethod
    def response_class(cls) -> type["PrismeSELAccountResponse"]:
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

    def __init__(self):
        self._client = None

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
                logger.error("Failed connecting to prisme: %s" % str(e))
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
        self, request_object: PrismeRequest[ResponseType], debug_context: Any = None
    ) -> List[ResponseType]:
        if debug_context is not None:
            log_context = str(debug_context) + " "
        else:
            log_context = ""
        try:
            soap_request_class = self.client.get_type("tns:GWSRequestDCFUJ")
            response_class: type[ResponseType] = request_object.response_class()
            request = soap_request_class(
                requestHeader=self.create_request_header(request_object.method()),
                xmlCollection=self.create_request_body(request_object.xml),
            )
            logger.debug(
                "%sSending to %s:\n%s"
                % (log_context, request_object.method(), request_object.xml)
            )
            # soap_response is of type GWSReplyDCFUJ,
            # a dynamically specified class from the WDSL
            soap_response = self.client.service.processService(request)

            # soap_response.status is of type GWSReplyStatusDCFUJ
            if soap_response.status.replyCode != 0:
                raise PrismeException(
                    soap_response.status.replyCode,
                    soap_response.status.replyText,
                    debug_context,
                )

            outputs = []
            # soap_response_item is of type GWSReplyInstanceDCFUJ
            for (
                soap_response_item
            ) in soap_response.instanceCollection.GWSReplyInstanceDCFUJ:
                if soap_response_item.replyCode == 0:
                    logger.debug(
                        "%sReceiving from %s:\n%s"
                        % (log_context, request_object.method(), soap_response_item.xml)
                    )
                    outputs.append(
                        response_class(request_object, soap_response_item.xml)
                    )
                else:
                    raise PrismeException(
                        soap_response_item.replyCode,
                        soap_response_item.replyText,
                        debug_context,
                    )
            return outputs
        except Exception as e:
            logger.error(
                "%sError in process_service for %s: %s"
                % (log_context, request_object.method(), str(e))
            )
            raise e

    def get_account_data(
        self,
        cvr: str | int,
        date_from: date,
        date_to: date,
        debug_context: str | None = None,
    ) -> List[PrismeSELAccountResponse]:
        if debug_context is None:
            debug_context = {"method": "get_account_data", "cvr": cvr}
        return self.process_service(
            PrismeSELAccountRequest(cvr, date_from, date_to), debug_context
        )
