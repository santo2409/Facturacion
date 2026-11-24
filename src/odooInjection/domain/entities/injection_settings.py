"""Configuración que se revisa en cada corrida de la inyección (E-04).

En ETL-Avancys eran constantes editadas a mano en `Pipeline.py:147-175`. Aquí viven en
un Excel de configuración que el usuario edita (`configuracion_inyeccion.xlsx`).
`valores_del_etl()` trae los valores que tenía Pipeline.py en el commit 7bb6784.
"""

from dataclasses import dataclass, field


@dataclass
class InjectionSettings:
    # NIT limpio → motivo. El NIT existe en Odoo pero apunta a otro tercero.
    nits_bloqueados: dict[str, str] = field(default_factory=dict)
    # Prefijo del nombre (se compara normalizado, sin tildes) → motivo.
    empresas_bloqueadas: dict[str, str] = field(default_factory=dict)
    # NIT limpio → id de la factura ya subida en una corrida anterior del MISMO lote.
    ya_subidas: dict[str, object] = field(default_factory=dict)


def valores_del_etl() -> InjectionSettings:
    return InjectionSettings(
        nits_bloqueados={
            "830121897": "El Excel lo llama IPS GUADALUPE SAS pero en Odoo es AQUIA S.A.S.; "
                         "IPS GUADALUPE existe aparte con NIT 901835329",
            "900448167": "El Excel lo llama COMPONENTE SERVIEX SAS pero en Odoo es "
                         "DIGITALBNK SERVICIOS TRANSACCIONALES SAS",
        },
        empresas_bloqueadas={
            "SGS COLOMIA": "Error en libro consolidado",
        },
        ya_subidas={},
    )
