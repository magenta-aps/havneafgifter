import os

PRISME = {
    "customer_group": os.environ.get("PRISME_CUSTOMER_GROUP", "000000"),
    "currency_code": os.environ.get("PRISME_CURRENCY_CODE", "DKK"),
    "department_recid": os.environ.get("PRISME_DEPARTMENT_RECID"),
    "invoice_ean": os.environ.get("PRISME_INVOICE_EAN"),
    "order_form_num": os.environ.get("PRISME_ORDER_FORM_NUM"),
    "contact_person_id": os.environ.get("PRISME_CONTACT_PERSON_ID"),
    "project_name": os.environ.get("PRISME_PROJECT_NAME", "Unnuineq"),
    "project_category_id": int(os.environ.get("PRISME_PROJECT_CATEGORY_ID", "1")),
    "finance_law_id": os.environ.get("PRISME_FINANCE_LAW_ID", 0),
    "purpose_id": os.environ.get("PRISME_PURPOSE_ID", 0),
    "type_account_plan_id": os.environ.get("PRISME_TYPE_ACCOUNT_PLAN_ID", 0),
    "beneficiary": os.environ.get("PRISME_BENEFICIARY"),
    "wsdl": os.environ.get("PRISME_WSDL", ""),
    "auth": {
        "basic": {
            "username": os.environ.get("PRISME_USERNAME", ""),
            "domain": os.environ.get("PRISME_DOMAIN", ""),
            "password": os.environ.get("PRISME_PASSWORD", ""),
        }
    },
    "proxy": {"socks": os.environ.get("PRISME_SOCKS", None)},
    "mock": os.environ.get("PRISME_MOCK", False),
    "type_account": {
        "by_owner": {
            # Ship owners are compared to the keys here.
            # If a key is contained in the form's ship owner, we use the value
            "Royal Arctic Line A/S": os.environ.get("PRISME_TYPE_ACCOUNT_RAL", 0),
        },
        "other": os.environ.get("PRISME_TYPE_ACCOUNT_OTHER", 0),
        "cruise_lt_30k": os.environ.get("PRISME_TYPE_ACCOUNT_CRUISE_LT_30K", 0),
        "cruise_gte_30k": os.environ.get("PRISME_TYPE_ACCOUNT_CRUISE_GTE_30K", 0),
        "passenger_tax": os.environ.get("PRISME_TYPE_ACCOUNT_PASSENGER_TAX", 0),
        "landing_tax": os.environ.get("PRISME_TYPE_ACCOUNT_LANDING_TAX", 0),
    },
    "override_due_date": os.environ.get("OVERRIDE_DUE_DATE", None),
    "override_date": os.environ.get("OVERRIDE_DATE", None),
}
