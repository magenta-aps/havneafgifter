from datetime import date, timedelta
from unittest.mock import patch

from django.test import TestCase
from prisme import Prisme, PrismeSELAccountResponse

from havneafgifter.prisme import PrismeSELAccountResponseTransaction


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


class PrismeTestCase(TestCase):
    def setUp(self):
        super().setUp()

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
        transaction: PrismeSELAccountResponseTransaction = responses[0].transactions[0]
        self.assertEqual(transaction.invoice_number, invoice_number)
        self.assertEqual(transaction.accounting_date, accounting_date)
