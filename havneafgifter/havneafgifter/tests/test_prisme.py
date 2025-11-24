from datetime import date, timedelta
from unittest.mock import MagicMock, PropertyMock, patch

from django.test import TestCase

from havneafgifter.prisme import (
    Prisme,
    PrismeException,
    PrismeSELAccountRequest,
    PrismeSELAccountResponse,
    PrismeSELAccountResponseTransaction,
)


def strip_internal_whitespace(text: str) -> str:
    return "\n".join([line.strip() for line in text.split("\n")])


def prisme_sel_mock(invoice_number: str, accounting_date: date):
    xml = f"""
    <CustTable>
        <TotalClaim>-300.00</TotalClaim>
        <TotalPayment>-62.00</TotalPayment>
        <TotalSum>-362.00</TotalSum>
        <TotalRestance>-362.00</TotalRestance>
        <CustTrans>
            <AccountNum>00064305</AccountNum>
            <TransDate>2021-07-01</TransDate>
            <AccountingDate>{accounting_date.isoformat()}</AccountingDate>
            <CustGroup>201021</CustGroup>
            <CustGroupName>AMA 2021</CustGroupName>
            <Voucher>RNT-00058035</Voucher>
            <Txt>Testing</Txt>
            <CustPaymCode></CustPaymCode>
            <CustPaymDescription></CustPaymDescription>
            <AmountCur>0.19</AmountCur>
            <RemainAmountCur>0.19</RemainAmountCur>
            <DueDate>2021-07-01</DueDate>
            <Closed></Closed>
            <LastSettleVoucher></LastSettleVoucher>
            <CollectionLetterDate></CollectionLetterDate>
            <CollectionLetterCode>Ingen</CollectionLetterCode>
            <Invoice>123</Invoice>
            <TransType>Renter</TransType>
            <ClaimTypeCode></ClaimTypeCode>
            <RateNmb></RateNmb>
            <ExternalInvoiceNumber>{invoice_number}</ExternalInvoiceNumber>
        </CustTrans>
    </CustTable>
    """
    return PrismeSELAccountResponse(None, xml)


class PrismeTest(TestCase):

    @patch.object(Prisme, "get_account_data")
    def test_get_account_data(self, get_account_data_mock):
        accounting_date = date(2025, 12, 1)
        invoice_number = "TAL-1234"
        get_account_data_mock.return_value = [
            prisme_sel_mock(invoice_number, accounting_date)
        ]
        prisme = Prisme()
        responses = prisme.get_account_data(
            12345678,
            accounting_date - timedelta(days=1),
            accounting_date + timedelta(days=1),
        )
        self.assertEqual(len(responses), 1)
        self.assertEqual(len(responses[0].transactions), 1)
        transaction: PrismeSELAccountResponseTransaction = responses[0][0]
        self.assertEqual(transaction.extern_invoice_number, invoice_number)
        self.assertEqual(transaction.accounting_date, accounting_date)


class PrismeSELAccountRequestTest(TestCase):

    maxDiff = None

    @classmethod
    def setUpTestData(cls):
        cls.request = PrismeSELAccountRequest(
            12345678, date(2025, 1, 1), date(2025, 1, 31)
        )

    def test_method(self):
        self.assertEqual(self.request.method(), "getAccountStatementSEL")

    def test_xml(self):
        self.assertEqual(
            strip_internal_whitespace(self.request.xml),
            strip_internal_whitespace(
                """<CustTable>
                <CustIdentificationNumber>12345678</CustIdentificationNumber>
                <CustInterestCalc>Åbne og Lukkede</CustInterestCalc>
                <FromDate>2025-01-01</FromDate>
                <ToDate>2025-01-31</ToDate>
                </CustTable>"""
            ),
        )

    def test_exception_nonzero_status(self):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.status.replyCode = 1
        mock_response.status.replyText = "Test Error"
        mock_client.service.processService.return_value = mock_response
        with patch.object(
            Prisme, "client", new_callable=PropertyMock(return_value=mock_client)
        ):
            prisme = Prisme()
            with self.assertRaises(PrismeException) as exception_cm, self.assertLogs(
                "havneafgifter.prisme", level="ERROR"
            ) as log_cm:
                prisme.get_account_data(12345678, date(2025, 1, 1), date(2025, 1, 31))
            exception = exception_cm.exception
            self.assertEqual(exception.code, 1)
            self.assertEqual(exception.text, "Test Error")
            self.assertEqual(
                exception.context, {"method": "get_account_data", "cvr": 12345678}
            )
            self.assertEqual(
                log_cm.output,
                [
                    "ERROR:havneafgifter.prisme:"
                    "{'method': 'get_account_data', 'cvr': 12345678} "
                    "Error in process_service for getAccountStatementSEL: "
                    "Error in response from Prisme. Code: 1, Text: Test Error"
                ],
            )
