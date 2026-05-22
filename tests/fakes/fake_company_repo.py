class FakeCompanyRepo:
    def __init__(self, initial=None):
        self._data = initial or []
        self._packages = []
        self._next_id = max((c["id"] for c in self._data), default=0) + 1

    def find_by_nit(self, nit):
        row = next((c for c in self._data if c["nit"] == nit), None)
        return (row["id"], row["nit"], row["name"]) if row else None

    def find_by_name(self, name):
        row = next((c for c in self._data if c["name"].strip().upper() == name.strip().upper()), None)
        return (row["id"], row["nit"], row["name"]) if row else None

    def save(self, company):
        existing_name = self.find_by_name(company.name)
        if existing_name and existing_name[1] != company.nit:
            return None
        existing = next((c for c in self._data if c["nit"] == company.nit), None)
        if existing:
            existing["name"] = company.name
            return (existing["id"], existing["nit"], existing["name"])
        entry = {"id": self._next_id, "nit": company.nit, "name": company.name}
        self._data.append(entry)
        self._next_id += 1
        return (entry["id"], entry["nit"], entry["name"])

    def save_batch(self, companies):
        return [self.save(c) for c in companies]

    def all(self):
        return list(self._data)

    def companies_packages_all(self):
        return list(self._packages)

    def companies_packages_batch(self, batch):
        for cp in batch:
            existing = next((p for p in self._packages if p["company"] == cp.company_id), None)
            if existing:
                existing["package"] = cp.package_id
                existing["model"] = cp.model
            else:
                self._packages.append({"company": cp.company_id, "package": cp.package_id, "model": cp.model})
