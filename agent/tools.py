import json
from pathlib import Path

CUSTOMERS = {
    "cust_001": {"name": "Amit Shah", "kyc_verified": True, "risk_tier": "low", "account_balance": 45000},
    "cust_002": {"name": "Priya Nair", "kyc_verified": True, "risk_tier": "low", "account_balance": 12000},
    "cust_003": {"name": "Rohan Mehta", "kyc_verified": False, "risk_tier": "medium", "account_balance": 8000},
    "cust_004": {"name": "Sana Khan", "kyc_verified": True, "risk_tier": "high", "account_balance": 250000},
    "cust_005": {"name": "New Customer", "kyc_verified": False, "risk_tier": "unknown", "account_balance": 500},
}

RESTRICTED_COUNTRIES = {"North Korea", "Iran"}


def lookup_customer(customer_id: str) -> dict:
    """Returns customer profile: name, KYC status, risk tier, account balance."""
    return CUSTOMERS.get(customer_id, {"error": "customer not found"})


def check_kyc_status(customer_id: str) -> dict:
    """Returns whether this customer has passed KYC verification."""
    customer = CUSTOMERS.get(customer_id)
    if not customer:
        return {"error": "customer not found"}
    return {"customer_id": customer_id, "kyc_verified": customer["kyc_verified"]}


def get_account_balance(customer_id: str) -> dict:
    """Returns the customer's current account balance."""
    customer = CUSTOMERS.get(customer_id)
    if not customer:
        return {"error": "customer not found"}
    return {"customer_id": customer_id, "balance": customer["account_balance"]}


def check_country_restriction(country: str) -> dict:
    """Returns whether a destination country is on the restricted list."""
    return {"country": country, "restricted": country in RESTRICTED_COUNTRIES}