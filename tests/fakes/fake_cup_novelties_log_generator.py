from pathlib import Path


class FakeCupNoveltiesLogGenerator:
    FILENAME = "novedades_cups.xlsx"

    def __init__(self):
        self.calls = []

    def generate(self, novelties, output_dir: Path) -> Path:
        self.calls.append((novelties, output_dir))
        return output_dir / self.FILENAME
