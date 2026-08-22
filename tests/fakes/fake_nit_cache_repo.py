class FakeNitCacheRepo:
    def __init__(self, cached=None):
        self._cached = cached or {}
        self.saved = []

    def get_many(self, nits):
        wanted = {str(n) for n in nits}
        return {n: r for n, r in self._cached.items() if n in wanted}

    def save_many(self, results):
        self.saved.extend(results)
