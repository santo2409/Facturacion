"""Lo que la corrida no pudo subir: acumuladores de ETL-Avancys (`Pipeline.py:1314-1386`).

  pendientes  -> una fila por examen que quedó por fuera (lo sube el facturador a mano).
  revisar     -> una fila por ciudad o código problemático (qué arreglar en Odoo).
  sin_factura -> una fila por empresa que no se facturó entera.

Se conservan los tipos (`int` 0 / `float`) del ETL porque llegan a los libros (D-2).
Se copia también el doble conteo de `revisar` si una empresa se reintenta (E-09).
"""

from src.odooInjection.domain.entities.etl_constants import COLS_FIJAS, NUM_COLS_FIJAS


class PendingRegistry:
    def __init__(self):
        self.pendientes: list[dict] = []
        self.revisar: dict = {}
        self.sin_factura: list[dict] = []

    def registrar_sin_factura(self, nit, empresa, pacientes, todas_cols_examenes, motivo):
        """Registra una empresa que se va entera a VERIFICAR, con lo que arrastra."""
        examenes = valor = 0
        cedulas = set()
        idx_ced = COLS_FIJAS.index("N Identificacion")
        for p in pacientes:
            cedulas.add(str(p[idx_ced]))
            for i, cod in enumerate(todas_cols_examenes):
                v = p[NUM_COLS_FIJAS + i] if cod else None
                if v:
                    examenes += 1
                    if isinstance(v, (int, float)):
                        valor += v
        falta_nit = "Sin tercero" in motivo or "NIT invalido" in motivo
        self.sin_factura.append({
            "nit": nit, "empresa": empresa, "pacientes": len(cedulas),
            "examenes": examenes, "valor": valor, "motivo": motivo,
            "accion": ("CREAR EL TERCERO en Odoo con ese NIT en 'Numero de "
                       "identificacion' y volver a correr el Pipeline"
                       if falta_nit else
                       "Revisar el motivo y subir la factura a mano"),
            "que_falta": "NIT POR CREAR" if falta_nit else "OTRO",
        })

    def pendiente(self, paciente, nit, empresa, codigo, valor, tipo, motivo) -> dict:
        """Una fila del libro de pendientes, con lo que el facturador necesita para crear la línea a mano."""
        def campo(nombre):
            try:
                return paciente[COLS_FIJAS.index(nombre)]
            except (ValueError, IndexError):
                return None
        ciudad = campo("Ciudad")
        fila = {
            "nit": nit,
            "empresa": empresa,
            "paciente": campo("Paciente"),
            "cedula": campo("N Identificacion"),
            "ciudad": ciudad or "(vacia)",
            "sede": campo("Sede"),
            "fecha": campo("Fecha Ingreso"),
            "tipo_examen": campo("Tipo Examen"),
            "codigo": codigo,
            "valor": valor if isinstance(valor, (int, float)) else "",
            "problema": tipo,
            "motivo": motivo or "",
            "factura_id": "",
        }
        clave = (tipo, fila["ciudad"] if tipo == "SIN CUENTA ANALITICA" else codigo)
        r = self.revisar.setdefault(clave, {
            "problema": tipo, "que": clave[1], "motivo": motivo or "",
            "examenes": 0, "pacientes": set(), "empresas": set(),
            "valor": 0.0, "sedes": set(),
        })
        r["examenes"] += 1
        r["pacientes"].add(str(fila["cedula"]))
        r["empresas"].add(str(empresa))
        if fila["sede"]:
            r["sedes"].add(str(fila["sede"]))
        if isinstance(valor, (int, float)):
            r["valor"] += valor
        return fila

    def guardar_pendientes(self, pendientes, factura_id):
        for p in pendientes:
            p["factura_id"] = factura_id
        self.pendientes.extend(pendientes)
