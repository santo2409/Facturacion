"""Resolución de la cuenta analítica de un paciente (sede + ciudad).

Copia de `resolver_cuenta_analitica` y `_indice_cuentas` de ETL-Avancys
(`Pipeline.py:388-407`, `633-788`). Orden: 1) la sede tiene cuenta propia,
2) la sede dice EXTRAMURAL, 3) la ciudad va por id, 4) la ciudad está en el mapa
(confirmada por el nombre), 5) la ciudad no está en el mapa → PROVEEDORES por nombre.
Si no se puede imputar con certeza, devuelve (None, None, motivo) y el paciente se aparta.
"""

from src.odooInjection.domain.entities.etl_constants import (
    FAMILIA_EXTRAMURAL,
    FAMILIA_PROVEEDOR,
    SEDES_EXTRAMURALES,
)
from src.odooInjection.domain.services.city_key import (
    SEDE_CUENTA_CLAVE,
    clave_ciudad,
    clave_en_indice,
    cuenta_por_ciudad,
    elegir_rama,
    familia_de,
    normalizar,
)


class AnalyticAccountResolver:
    def __init__(self, gateway, logger):
        self._gateway = gateway
        self._logger = logger
        self._indice: dict = {}
        self._por_codigo: dict = {}

    def indice(self) -> dict:
        """{(clave_ciudad, familia): [cuentas]} con TODAS las cuentas de Odoo (una consulta por corrida)."""
        if self._indice:
            return self._indice
        cuentas = self._gateway.analytic_accounts_all()
        for c in cuentas:
            ciudad = c["name"].split(" - ")[-1].strip()
            self._indice.setdefault(
                (clave_ciudad(ciudad), familia_de(c["name"])), []).append(c)
        self._logger.info("Indice de cuentas analiticas: " + str(len(cuentas)) +
                          " cuentas, " + str(len(self._indice)) + " combinaciones ciudad+familia")
        return self._indice

    def _cuentas_por_codigo(self, codigo):
        """Todas las cuentas con ese código, sin limit: el código no es único en Odoo."""
        if codigo not in self._por_codigo:
            self._por_codigo[codigo] = self._gateway.analytic_accounts_by_code(codigo)
        return self._por_codigo[codigo]

    def resolver(self, ciudad_raw, sede_raw=None):
        """Devuelve (id_cuenta, etiqueta, motivo)."""
        indice = self.indice()

        def por_indice(familia, porque):
            clave, fallo = clave_en_indice(indice, ciudad_raw)
            if not clave:
                return None, None, (fallo or
                                    "Ninguna cuenta analitica de Odoo se llama como "
                                    "la ciudad '" + str(ciudad_raw) + "'")
            candidatas = indice.get((clave, familia), [])
            if not candidatas:
                return None, None, (
                    "No hay cuenta analitica " + familia + " para '" +
                    str(ciudad_raw) + "'" + porque + " — hay que crearla en Odoo")
            cuenta, fallo = elegir_rama(candidatas)
            if not cuenta:
                return None, None, (fallo + " (ciudad '" + str(ciudad_raw) +
                                    "', familia " + familia + ")")
            return cuenta["id"], cuenta["name"], None

        # ── 1. La sede tiene cuenta propia (SEDE 103, ZONA INDUSTRIAL) ──
        clave_sede = clave_ciudad(sede_raw)
        if clave_sede in SEDE_CUENTA_CLAVE:
            cod_sede = SEDE_CUENTA_CLAVE[clave_sede]
            cuentas = self._cuentas_por_codigo(cod_sede)
            if len(cuentas) != 1:
                return None, None, (
                    "La sede '" + str(sede_raw) + "' apunta al codigo " + cod_sede +
                    ", que en Odoo devuelve " + str(len(cuentas)) + " cuentas")
            ciudad_cuenta = clave_ciudad(cuentas[0]["name"].split(" - ")[-1])
            if ciudad_cuenta != clave_ciudad(ciudad_raw):
                return None, None, (
                    "La sede '" + str(sede_raw) + "' esta mapeada a " + cod_sede +
                    " (" + cuentas[0]["name"].split(" - ")[-1] + ") pero la fila "
                    "dice ciudad '" + str(ciudad_raw) + "' — revisar SEDE_CUENTA")
            return cuentas[0]["id"], cuentas[0]["name"], None

        # ── 2. La sede dice EXTRAMURAL: va a la extramural de su ciudad ──
        sede_norm = normalizar(str(sede_raw or ""))
        if any(p in sede_norm for p in SEDES_EXTRAMURALES):
            return por_indice(FAMILIA_EXTRAMURAL,
                              " (la sede dice '" + str(sede_raw) + "')")

        codigo, cuenta_id, _como, motivo = cuenta_por_ciudad(ciudad_raw)

        # ── 3. La ciudad va por id (cuenta sin código en Odoo) ──
        if cuenta_id:
            r = self._gateway.analytic_account_read(cuenta_id)
            if not r:
                return None, None, ("La cuenta analitica id=" + str(cuenta_id) +
                                    " de '" + str(ciudad_raw) + "' ya no existe en Odoo")
            return cuenta_id, r[0]["name"], None

        # ── 4. La ciudad está en el mapa: el código da la familia, la cuenta se confirma por nombre ──
        if codigo:
            cuentas = self._cuentas_por_codigo(codigo)
            if not cuentas:
                familias = {f for (k, f) in indice if k == clave_ciudad(ciudad_raw)}
                fam = familias.pop() if len(familias) == 1 else FAMILIA_PROVEEDOR
                cid, etiqueta, fallo = por_indice(
                    fam, " (el codigo " + codigo + " del mapa ya no existe en Odoo)")
                if cid:
                    self._logger.warning(
                        "  El codigo " + codigo + " de '" + str(ciudad_raw) +
                        "' ya no existe en Odoo: se uso la cuenta por nombre"
                        " -> " + str(etiqueta) + ". Hay que actualizar "
                        "CIUDAD_CUENTA en etl_constants.py")
                    return cid, etiqueta, None
                return None, None, fallo
            clave = clave_ciudad(ciudad_raw)

            def cola(c):
                return clave_ciudad(c["name"].split(" - ")[-1])

            exactas = [c for c in cuentas if cola(c) == clave]
            if len(exactas) == 1:
                return exactas[0]["id"], exactas[0]["name"], None
            if not exactas:
                parciales = [c for c in cuentas if cola(c).endswith(clave)]
                if len(parciales) == 1:
                    return parciales[0]["id"], parciales[0]["name"], None
                familia = familia_de(cuentas[0]["name"])
                cid, etiqueta, fallo = por_indice(
                    familia, " (el codigo " + codigo + " del mapa apunta a " +
                    cuentas[0]["name"].split(" - ")[-1] + ")")
                if cid:
                    self._logger.warning(
                        "  El codigo " + codigo + " del mapa no es de '" +
                        str(ciudad_raw) + "': se uso la cuenta por nombre -> " +
                        str(etiqueta))
                    return cid, etiqueta, None
                return None, None, fallo
            return None, None, (
                "El codigo " + codigo + " esta repetido y " + str(len(exactas)) +
                " de sus cuentas se llaman '" + str(ciudad_raw) + "': " +
                ", ".join(str(c["id"]) for c in exactas))

        # ── 5. La ciudad NO está en el mapa: se busca por nombre (PROVEEDORES) ──
        cid, etiqueta, fallo = por_indice(FAMILIA_PROVEEDOR, "")
        if cid:
            self._logger.warning(
                "  Ciudad '" + str(ciudad_raw) + "' no esta en el mapa: se "
                "encontro su cuenta por nombre -> " + str(etiqueta) +
                ". Conviene agregarla a CIUDAD_CUENTA")
            return cid, etiqueta, None
        return None, None, (motivo or fallo)
