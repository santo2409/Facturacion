from src.scrapping.domain.exceptions import NitCacheSaveError


class FakeNitCacheRepo:
    def __init__(self, cached=None, cached_by_name=None, omit=None, fail=False):
        self._cached = cached or {}
        self._cached_by_name = cached_by_name or {}
        self._omit = [str(o) for o in (omit or [])]
        self._fail = fail
        self.saved = []

    def get_many(self, nits):
        wanted = {str(n) for n in nits}
        return {n: r for n, r in self._cached.items() if n in wanted}

    def get_by_names(self, names):
        wanted = set(names)
        return {n: r for n, r in self._cached_by_name.items() if n in wanted}

    def save_many(self, results):
        self.saved.extend(results)
        saved_nits = {str(r.nit) for r in results}
        return [nit for nit in self._omit if nit in saved_nits]
