from rich.progress import BarColumn, Progress, TextColumn, TimeElapsedColumn


class RichProgress:
    def __init__(self):
        self.progress = None
        self.task = None
        self._total = None

    def __call__(self, description, total):
        self._total = total
        self.progress = Progress(
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            "[progress.percentage]{task.percentage:>3.0f}%",
            TimeElapsedColumn(),
        )
        self.task = self.progress.add_task(description, total=total)
        return self

    def __enter__(self):
        self.progress.start()
        return self

    def advance(self):
        self.progress.update(self.task, advance=1)

    def __exit__(self, exc_type, *args):
        if exc_type is None:
            self.progress.update(self.task, completed=self._total)
        self.progress.stop()
