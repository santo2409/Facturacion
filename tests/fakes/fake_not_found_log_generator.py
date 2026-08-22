class FakeNotFoundLogGenerator:
    def __init__(self):
        self.calls = []

    def generate(self, results, output_dir):
        self.calls.append((results, output_dir))
