from dataclasses import dataclass


@dataclass
class InvoiceLine:
    product_code: str
    quantity: int
    analytic_account_code: str
