from src.scrapping.domain.entities.nit_result import NitResult


class FakeNitService:
    def __init__(self, results=None, by_name_result=None):
        self._results = results or []
        self._by_name_result = by_name_result
        self._written = None

    def search(self, nits):
        return self._results

    def search_by_name(self, name):
        return self._by_name_result

    def writer(self, data, file_path):
        self._written = (data, file_path)
