"""Tests para RichProgress - validar que la barra llega al 100%."""
from unittest.mock import patch, MagicMock

from src.shared.console.progress import RichProgress


def test_progress_completes_to_100_on_exit():
    progress = RichProgress()
    with progress("Test", total=3):
        progress.advance()
        progress.advance()
        progress.advance()

    task = progress.progress.tasks[0]
    assert task.completed == task.total


def test_progress_forces_100_even_if_advances_incomplete():
    progress = RichProgress()
    with progress("Test", total=5):
        progress.advance()
        progress.advance()
        # Only 2 of 5 advances, but no exception

    task = progress.progress.tasks[0]
    assert task.completed == task.total


def test_progress_does_not_force_100_on_exception():
    progress = RichProgress()
    try:
        with progress("Test", total=5):
            progress.advance()
            raise ValueError("error")
    except ValueError:
        pass

    task = progress.progress.tasks[0]
    assert task.completed == 1  # Only 1 advance was made


def test_progress_reusable_across_calls():
    progress = RichProgress()

    with progress("First", total=2):
        progress.advance()
        progress.advance()

    first_task = progress.progress.tasks[0]
    assert first_task.completed == first_task.total

    with progress("Second", total=3):
        progress.advance()
        progress.advance()
        progress.advance()

    second_task = progress.progress.tasks[0]
    assert second_task.completed == second_task.total
