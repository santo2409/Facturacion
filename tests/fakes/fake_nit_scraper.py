from src.scrapping.domain.entities.nit_result import NitResult


class FakeNitScraper:
    """Fake del puerto NitScraperRepository con registro de llamadas.

    `omit` permite simular el comportamiento real del scraper de RUES, que
    puede devolver menos resultados que NITs de entrada.
    """

    def __init__(self, by_nit=None, by_name=None, omit=None):
        self._by_nit = by_nit or {}
        self._by_name = by_name or {}
        self._omit = {str(o) for o in (omit or [])}
        self.search_nits_calls = []
        self.search_by_name_calls = []
        self.search_names_calls = []

    def search_nits(self, nits, show_progress=False):
        self.search_nits_calls.append(list(nits))
        results = []
        for nit in nits:
            if str(nit) in self._omit:
                continue
            hit = self._by_nit.get(str(nit))
            results.append(hit if hit else NitResult(nit=nit, is_company=False))
        return results

    def search_by_name(self, name):
        self.search_by_name_calls.append(name)
        return self._by_name.get(name)

    def search_names(self, names, show_progress=False):
        self.search_names_calls.append(list(names))
        return {name: self._by_name[name] for name in names if name in self._by_name}
