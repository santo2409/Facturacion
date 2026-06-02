class FakeOdooRepo:
    def __init__(self, products=None, clients=None):
        self._products = products or {}
        self._clients = clients or {}
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

    def create_client(self, nit, name):
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
