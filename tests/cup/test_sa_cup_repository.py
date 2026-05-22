"""Tests para SaCupRepository con mock de Session."""
from unittest.mock import MagicMock

from src.cup.infrastructure.persistence.sa_cup_repository import SaCupRepository


def test_get_all_cups_returns_list():
    session = MagicMock()
    row1 = MagicMock(id=1, code="890201", name="HEMOGRAMA")
    row2 = MagicMock(id=2, code="890301", name="PERFIL")
    session.query.return_value.all.return_value = [row1, row2]

    repo = SaCupRepository(session)
    result = repo.get_all_cups()
    assert isinstance(result, list)
