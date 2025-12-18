from rich.progress import BarColumn, Progress, TextColumn, TimeElapsedColumn


class RichProgress:
    def __init__(self):
        self.progress = None
        self.task = None

    def __call__(self, description, total):
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

    def __exit__(self, *args):
        self.progress.stop()
