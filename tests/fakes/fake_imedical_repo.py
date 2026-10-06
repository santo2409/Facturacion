from src.company.domain.repositories.imedical_repository import ImedicalRepository


class FakeImedicalRepo(ImedicalRepository):
    def __init__(self, initial=None):
        # initial: [{"nit_error","name","nit_success","name_error"}]
        self._data = {row["nit_error"]: dict(row) for row in (initial or [])}
        self.saved_batches = []  # espía: cada llamada a save_batch (lista de ImedicalCorrection)

    def all(self):
        return list(self._data.values())

    def save_batch(self, corrections):
        self.saved_batches.append(list(corrections))
        for c in corrections:
            self._data[c.nit_error] = {
                "nit_error": c.nit_error,
                "name": c.name,
                "nit_success": c.nit_success,
                "name_error": c.name_error,
            }
        return len(corrections)
