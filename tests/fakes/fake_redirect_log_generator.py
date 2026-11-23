class FakeRedirectLogGenerator:
    def __init__(self):
        self.calls = []  # [(rows, output_dir), ...]

    def generate(self, rows, output_dir):
        self.calls.append((rows, output_dir))
        return output_dir / "empresas_redirigidas.xlsx"
