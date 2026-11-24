from src.odooInjection.domain.repositories.injection_report_writer import InjectionReportWriter


class FakeInjectionReportWriter(InjectionReportWriter):
    def __init__(self):
        self.verificar: list[str] = []
        self.creadas: list[tuple] = []
        self.csv_iniciado = 0
        self.escrituras_de_libros = 0
        self.ultimos_resultados: list[dict] = []

    def copy_to_verificar(self, path):
        self.verificar.append(path.name)

    def start_created_log(self):
        self.csv_iniciado += 1

    def append_created(self, factura_id, nit, empresa, url):
        self.creadas.append((factura_id, nit, empresa, url))

    def write_books(self, resultados, registry, url_factura):
        self.escrituras_de_libros += 1
        self.ultimos_resultados = [dict(r) for r in resultados]
