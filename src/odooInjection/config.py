import os
from datetime import date, timedelta

from src.shared.env import load_env

load_env()


def _fecha_servicio() -> str:
    return (date.today().replace(day=1) - timedelta(days=1)).strftime("%Y-%m-%d")


def get_odoo_config() -> dict:
    return {
        "url": os.getenv("ODOO_URL", ""),
        "db": os.getenv("ODOO_DB", ""),
        "username": os.getenv("ODOO_USERNAME", ""),
        "api_key": os.getenv("ODOO_API_KEY", ""),
        "diario_id": int(os.getenv("ODOO_DIARIO_ID", "47")),
        "cuenta_ingresos_excluidos": int(
            os.getenv("ODOO_CUENTA_INGRESOS_EXCLUIDOS", "42653")
        ),
        "cuenta_ingresos_gravados": int(
            os.getenv("ODOO_CUENTA_INGRESOS_GRAVADOS", "42650")
        ),
        "cuenta_receivable": int(os.getenv("ODOO_CUENTA_RECEIVABLE", "40921")),
        "cuenta_payable": int(os.getenv("ODOO_CUENTA_PAYABLE", "41977")),
        "productos_gravados": os.getenv("ODOO_PRODUCTOS_GRAVADOS", "100006").split(","),
        "taxes": [
            os.getenv(
                "ODOO_TAX_AUTORRETENCION_RENTA", "AUTORRETENCION IMPUESTO RENTA 2%"
            ),
            os.getenv(
                "ODOO_TAX_AUTORRETENCION_COMPRAS",
                "AUTORRETENCION COMPRA IMPUESTO RENTA 2%",
            ),
        ],
        "nombre_uom": os.getenv("ODOO_UOM", "Unidades"),
        "fecha_servicio": _fecha_servicio(),
        "fecha_vencimiento_dias": int(os.getenv("ODOO_FECHA_VENCIMIENTO_DIAS", "30")),
    }
