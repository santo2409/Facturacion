class FakeCityRepo:
    def __init__(self, initial=None):
        self._data = initial or []
        self._next_id = max((c["id"] for c in self._data), default=0) + 1

    def save_batch(self, cities):
        results = []
        for c in cities:
            existing = next((x for x in self._data if x["name"] == c.name), None)
            if existing:
                results.append((existing["id"], existing["name"]))
            else:
                entry = {"id": self._next_id, "name": c.name}
                self._data.append(entry)
                results.append((entry["id"], entry["name"]))
                self._next_id += 1
        return results

    def all(self):
        return list(self._data)
