from src.scrapping.domain.entities.nit_result import NitResult


class FakeNitService:
    def __init__(self, results=None, by_name_result=None, local_updates=None, odoo_available=True):
        self._results = results or []
        self._by_name_result = by_name_result
        self._written = None
        self.called_with = None
        self.rues_cache = None
        self.local_updates = list(local_updates or [])
        self.odoo_available = odoo_available

    def search(self, nits, rues_cache=None):
        self.called_with = list(nits)
        self.rues_cache = rues_cache
        return self._results

    def search_by_name(self, name):
        return self._by_name_result

    def writer(self, data, file_path):
        self._written = (data, file_path)
