from pathlib import Path


class FakeDuplicateLogGenerator:
    FILENAME = "empresas_duplicadas.xlsx"

    def __init__(self):
        self.calls = []

    def generate(self, candidates, output_dir: Path) -> Path:
        self.calls.append((candidates, output_dir))
        return output_dir / self.FILENAME
