from dataclasses import dataclass


@dataclass
class InvoiceResult:
    nit: str
    empresa: str
    estado: str  # OK | VERIFICAR | ERROR
    detalle: str
    factura_id: int | None = None
    link: str = ""
    hora: str = ""
