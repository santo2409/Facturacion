from pathlib import Path

from src.cup.infrastructure.persistence.sa_cup_repository import SaCupRepository
from src.preInvoice.application.use_cases.split_by_nit import SplitByNit
from src.shared.console.progress import RichProgress
from src.shared.database.database import get_session
from src.shared.utils.console import console

CONSOLIDADO_PATH = Path("CONSOLIDADO.xlsx")
OUTPUT_DIR = Path("pre-facturas")


def generate_pre_invoices(logger):

    if not CONSOLIDADO_PATH.exists():
        logger.error(
            f"Archivo {CONSOLIDADO_PATH} no encontrado tras assign_rates.",
            user_msg="No se encontró el archivo CONSOLIDADO.xlsx. El proceso de asignación pudo haber fallado.",
        )
        console.print(
            f"[red]Archivo {CONSOLIDADO_PATH} no encontrado. No se pueden generar pre-facturas.[/red]",
            highlight=False,
        )
        return

    session = get_session()
    try:
        cup_repo = SaCupRepository(session)
        logger.info(
            f"Iniciando separación por NIT desde {CONSOLIDADO_PATH}",
            user_msg="Iniciando generación de archivos por NIT...",
        )
        SplitByNit(logger, cup_repo, RichProgress()).execute(CONSOLIDADO_PATH, OUTPUT_DIR)
        logger.info(
            "Cadena completa ejecutada: assign_rates → split por NIT.",
            user_msg="Pre-facturas generadas exitosamente.",
        )
    except Exception as e:
        logger.error(
            f"Error generando pre-facturas: {e}",
            exc_info=True,
            user_msg="Ocurrió un error al generar las pre-facturas.",
        )
    finally:
        session.close()
