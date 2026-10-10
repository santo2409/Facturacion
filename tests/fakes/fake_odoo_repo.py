class FakeOdooRepo:
    def __init__(self, products=None, clients=None, partner_rates=None, rate_lines=None):
        self._products = products or {}
        self._clients = clients or {}
        self._partner_rates = partner_rates or []
        self._rate_lines = rate_lines or []
        self.calls = {"find_partner_rates_batch": 0, "find_rate_lines": 0}
        self.write_attempts = []
        self._created_invoices = []
        self._next_invoice_id = 1000
        self._next_client_id = 500
        self._connected = False

    def connect(self):
        self._connected = True

    def find_product(self, code):
        return self._products.get(code)

    def find_client(self, nit, name):
        if nit in self._clients:
            c = self._clients[nit]
            return c["id"], c["name"], "NIT"
        return None, None, None

    def find_clients_batch(self, nits):
        result = {}
        for nit in nits:
            if nit in self._clients:
                c = self._clients[nit]
                result[nit] = (c["id"], c["name"], "NIT")
        return result

    def find_client_by_name(self, name):
        for nit, c in self._clients.items():
            if c["name"] == name:
                return c["id"], c["name"], "nombre"
        return None, None, None

    def find_clients_by_name(self, name, limit=10):
        term = (name or "").strip().upper()
        if not term:
            return []
        matches = []
        for nit, c in self._clients.items():
            candidate = c["name"].upper()
            if term in candidate or candidate in term:
                matches.append({"id": c["id"], "name": c["name"], "vat": nit})
            if len(matches) >= limit:
                break
        return matches

    def get_nit(self, client_id):
        for nit, c in self._clients.items():
            if c["id"] == client_id:
                return nit
        return None

    def find_partner_rates_batch(self, nits):
        self.calls["find_partner_rates_batch"] += 1
        wanted = set(nits)
        return [p for p in self._partner_rates if p["nit"] in wanted]

    def find_rate_lines(self, rate_ids, cup_codes):
        self.calls["find_rate_lines"] += 1
        rates, cups = set(rate_ids), set(cup_codes)
        return [l for l in self._rate_lines if l["rate_id"] in rates and l["cup"] in cups]

    def create_client(self, nit, name):
        self.write_attempts.append("create_client")
        cid = self._next_client_id
        self._next_client_id += 1
        self._clients[nit] = {"id": cid, "name": name}
        return cid

    def find_analytic_account(self, code):
        return 100

    def find_tax(self, name):
        return 10

    def find_uom(self, name):
        return 1

    def find_date_range(self, date):
        return 5

    def create_invoice(self, vals):
        fid = self._next_invoice_id
        self._next_invoice_id += 1
        self._created_invoices.append(vals)
        return fid
