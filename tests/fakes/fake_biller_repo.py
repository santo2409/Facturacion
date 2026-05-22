class FakeBillerRepo:
    def __init__(self, initial=None):
        self._data = initial or []
        self._next_id = max((b["id"] for b in self._data), default=0) + 1

    def find_by_name(self, name):
        row = next((b for b in self._data if b["name"] == name), None)
        return (row["id"], row["name"]) if row else None

    def save(self, biller):
        existing = next((b for b in self._data if b["name"] == biller.name), None)
        if existing:
            return (existing["id"], existing["name"])
        entry = {"id": self._next_id, "name": biller.name}
        self._data.append(entry)
        self._next_id += 1
        return (entry["id"], entry["name"])

    def save_batch(self, billers):
        results = []
        for b in billers:
            results.append(self.save(b))
        return results

    def all(self):
        return list(self._data)
