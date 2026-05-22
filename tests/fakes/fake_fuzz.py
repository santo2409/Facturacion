class FakeFuzz:
    """Fake fuzzy matcher that returns exact match or configurable result."""

    def __init__(self, override=None):
        self._override = override  # dict: input -> output

    def fuzz_property(self, name, catalog, threshold=90):
        if self._override and name in self._override:
            return self._override[name]
        # Exact match in catalog
        for item in catalog:
            if item["name"] == name:
                return name
        return None
