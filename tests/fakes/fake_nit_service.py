from src.scrapping.domain.entities.nit_result import NitResult


class FakeNitService:
    def __init__(self, results=None):
        self._results = results or []
        self._written = None

    def search(self, nits):
        return self._results

    def writer(self, data, file_path):
        self._written = (data, file_path)
