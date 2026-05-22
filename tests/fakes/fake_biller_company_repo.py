class FakeBillerCompanyRepo:
    def __init__(self):
        self._data = []

    def link_or_update(self, company_id, biller_id):
        existing = next((d for d in self._data if d["company"] == company_id), None)
        if existing:
            existing["biller"] = biller_id
        else:
            self._data.append({"company": company_id, "biller": biller_id})

    def link_or_update_batch(self, pairs):
        for company_id, biller_id in pairs:
            self.link_or_update(company_id, biller_id)

    def all(self):
        return list(self._data)
