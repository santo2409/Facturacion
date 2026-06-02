from pathlib import Path


class FakePreInvoiceReader:
    def __init__(self, filas=None, cols_examenes=None):
        self._filas = filas or []
        self._cols_examenes = cols_examenes or []

    def read_files(self, directory: Path):
        return self._filas, self._cols_examenes
