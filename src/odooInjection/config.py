import os

from src.shared.env import load_env

load_env()


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
    }


_VERDADERO = {"1", "true", "si", "sí", "yes", "on"}


def get_injection_config() -> dict:
    """Configuración propia de la carga de pre-facturas (opción 5), además de get_odoo_config.

    - ODOO_ACTUALIZAR_PRECIOS: dispara el botón "Actualizar precios" tras crear cada
      factura (ACTUALIZAR_PRECIOS del ETL). Apagado por defecto (E-05).
    - INYECCION_CONFIG_XLSX: Excel con NITs/empresas bloqueados y ya subidas (E-04).
    - INYECCION_SALIDA: carpeta base; cada corrida escribe en <base>/<AAAA-MM-DD_HHMM>/.
    """
    return {
        "actualizar_precios": os.getenv("ODOO_ACTUALIZAR_PRECIOS", "false").strip().lower() in _VERDADERO,
        "config_xlsx": os.getenv("INYECCION_CONFIG_XLSX") or "configuracion_inyeccion.xlsx",
        "salida": os.getenv("INYECCION_SALIDA") or "logs/cargar_prefacturas",
    }
