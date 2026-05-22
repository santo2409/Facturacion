class FakeActivityRepo:
    def __init__(self, initial=None):
        self._data = initial or [
            {"id": 1, "name": "INTRA"},
            {"id": 2, "name": "EXTRA"},
        ]

    def find_by_name(self, name):
        row = next((a for a in self._data if a["name"] == name), None)
        return (row["id"], row["name"]) if row else None

    def all(self):
        return list(self._data)
