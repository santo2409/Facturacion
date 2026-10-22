from abc import ABC, abstractmethod
from pathlib import Path

# Columnas de los libros de fase y de `sin_resolver`: una fila por llave original.
FINDING_COLUMNS = [
    "Fase", "Empresa", "NIT", "Paquete original", "Ciudad original", "CUP original",
    "Actividad", "Tarifa asignada", "Fuente de la tarifa", "Ciudad efectiva",
    "CUP efectivo", "Nº pacientes", "Qué debe hacer el área",
]
EXPIRED_COLUMNS = [
    "Empresa", "NIT", "Tarifa Odoo", "Tipo de tarifa", "Inicio vigencia", "Fin vigencia",
    "Estado Odoo", "Ciudad", "CUP", "Actividad", "Tarifa asignada", "Nº pacientes",
    "Qué debe hacer el área",
]
COMPANY_COLUMNS = ["NIT", "Empresa", "Motivo"]

EXPIRED_KEY = "odoo_tarifa_vencida"
COMPANIES_KEY = "empresas_odoo"

BOOK_DESCRIPTIONS = {
    "fase_01_paquete_propio_local": "Odoo no tiene la tarifa; se tomó de la base de datos local (paquete propio de la empresa). Debe cargarse en Odoo. «Paquete original» y «Fuente de la tarifa» coinciden porque la tarifa sale del propio paquete de la empresa.",
    "fase_02_paquete_c_2025": "El paquete propio no tiene tarifa; se asignó la de PAQUETE C 2025 (mismo CUP y ciudad).",
    "fase_03_cualquier_paquete": "Ni el paquete propio ni PAQUETE C 2025 tienen tarifa; se asignó la de otro paquete, proveedor o especial (mismo CUP y ciudad).",
    "fase_04_cup_base_paquete_c": "Sin tarifa para el CUP con sufijo; se asignó la de su CUP base en PAQUETE C 2025.",
    "fase_05_cup_base_cualquier_paquete": "Sin tarifa para el CUP con sufijo; se asignó la de su CUP base en otro paquete, proveedor o especial.",
    "fase_06_cualquier_ciudad": "Sin tarifa en la ciudad solicitada; se asignó la de otra ciudad (ver «Ciudad efectiva»).",
    "sin_resolver": "No existe tarifa en ninguna fase. En el CONSOLIDADO queda con valor 1 y debe crearse la tarifa.",
    EXPIRED_KEY: "Tarifas de Odoo con vigencia vencida que se asignaron igual; deben renovarse en Odoo.",
    COMPANIES_KEY: "Empresas sin tarifa en Odoo (no existen o no tienen tarifa especial ni base).",
}
COLUMN_HELP = {
    "Fase": "Fase de la cascada que resolvió el precio.",
    "Empresa": "Nombre de la empresa cliente.",
    "NIT": "NIT de la empresa (máximo 9 dígitos, sin dígito de verificación).",
    "Paquete original": "Paquete de la empresa en el que se buscó primero la tarifa (llave original).",
    "Ciudad original": "Ciudad solicitada en el consolidado (llave original).",
    "CUP original": "CUP del examen solicitado en el consolidado (llave original).",
    "Actividad": "Tipo de actividad: INTRA o EXTRA.",
    "Tarifa asignada": "Valor asignado, o «Sin tarifa» si no se resolvió.",
    "Fuente de la tarifa": "Tipo (Paquete, Proveedor, Especial) y nombre de donde salió la tarifa asignada.",
    "Ciudad efectiva": "Ciudad de la que salió la tarifa asignada.",
    "CUP efectivo": "CUP cuya tarifa se usó (el CUP base cuando se homologó).",
    "Nº pacientes": "Cantidad de filas del consolidado (pacientes) que comparten esta llave.",
    "Qué debe hacer el área": "Acción sugerida para el área de tarifas.",
    "Tarifa Odoo": "Nombre de la tarifa vencida en Odoo.",
    "Tipo de tarifa": "Especial (de la empresa) o Base.",
    "Inicio vigencia": "Fecha de inicio de vigencia en Odoo.",
    "Fin vigencia": "Fecha de fin de vigencia en Odoo; es anterior a la fecha de ejecución.",
    "Estado Odoo": "Estado de la tarifa en Odoo (approved / not_approved).",
    "Ciudad": "Ciudad de la línea de tarifa.",
    "CUP": "CUP del examen.",
    "Motivo": "Por qué la empresa no tiene tarifa en Odoo.",
}


class PhaseFindingsReporter(ABC):
    @abstractmethod
    def write(
        self, findings: dict[str, list[dict]], companies: list[dict], odoo_available: bool = True
    ) -> Path | None:
        """Escribe un libro por clave de `findings` con filas y `empresas_odoo.xlsx`
        si hay `companies`. `findings` trae una fila por celda (con paciente); el
        libro agrupa por llave. `odoo_available` indica si Odoo respondió en la ejecución. Devuelve la carpeta creada, o None si no hubo nada."""
