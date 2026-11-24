from src.company.domain.repositories.billing_redirect_repository import (
    BillingRedirectRepository,
)


class FakeBillingRedirectRepo(BillingRedirectRepository):
    def __init__(self, initial=None, falla=False):
        # initial: [{"nit_origen","nit_destino","etiqueta","name"}] (activas)
        self._data = {r["nit_origen"]: {**r, "activa": True} for r in (initial or [])}
        self._falla = falla

    def all(self):
        return [{k: v for k, v in r.items() if k != "activa"} for r in self._data.values() if r["activa"]]

    def upsert_many(self, rows):
        if self._falla:
            return None
        nuevas = actualizadas = 0
        for row in rows:
            if row["nit_origen"] in self._data:
                actualizadas += 1
            else:
                nuevas += 1
            self._data[row["nit_origen"]] = {**row, "activa": True}
        return nuevas, actualizadas

    def deactivate(self, nits_origen):
        hechas = []
        for nit in nits_origen:
            r = self._data.get(nit)
            if r and r["activa"]:
                r["activa"] = False
                hechas.append(nit)
        return hechas
