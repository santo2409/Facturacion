class FakeLogGenerator:
    def __init__(self, successful_nits=None):
        self.generated = []
        self._successful_nits = successful_nits or set()

    def generate(self, resultados, output_dir):
        self.generated.append((resultados, output_dir))

    def read_successful_nits(self, log_path):
        return self._successful_nits
