from src.company.domain.repositories.tian_repository import TianRepository


class FakeTianRepo(TianRepository):
    def __init__(self, initial=None):
        # initial: [{"nit_error","name"}]
        self._data = list(initial or [])

    def all(self):
        return list(self._data)
