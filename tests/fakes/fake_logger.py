class FakeLogger:
    def __init__(self):
        self.warnings = []
        self.infos = []
        self.errors = []

    def warning(self, msg, **_):
        self.warnings.append(msg)

    def info(self, msg, **_):
        self.infos.append(msg)

    def error(self, msg, **_):
        self.errors.append(msg)
