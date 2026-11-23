from src.company.domain.repositories.billing_redirect_repository import (
    BillingRedirectRepository,
)


class FakeBillingRedirectRepo(BillingRedirectRepository):
    def __init__(self, initial=None):
        # initial: [{"nit_origen","nit_destino","etiqueta","name"}]
        self._data = list(initial or [])

    def all(self):
        return list(self._data)
