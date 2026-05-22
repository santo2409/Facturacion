class FakeCupRepo:
    def __init__(self, data=None):
        self._data = data or []

    def exists(self, cup):
        return any(c["code"] == cup for c in self._data)

    def get_all_cups(self):
        return [c["code"] for c in self._data]

    def get_all(self):
        return list(self._data)
