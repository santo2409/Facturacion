class FakeProgress:
    """No-op progress bar for testing."""

    def __init__(self):
        self._advances = 0

    def __call__(self, description="", total=0):
        self._advances = 0
        return self

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def advance(self):
        self._advances += 1
