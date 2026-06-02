class FakeLogGenerator:
    def __init__(self):
        self.generated = []

    def generate(self, resultados, output_dir):
        self.generated.append((resultados, output_dir))
