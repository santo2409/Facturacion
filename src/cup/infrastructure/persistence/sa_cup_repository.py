from src.cup.domain.repositories.cup_repository import CupRepository
from src.shared.database.models import CupModel


class SaCupRepository(CupRepository):
    def __init__(self, session):
        self.session = session

    def exists(self, cup: str) -> bool:
        return self.session.query(CupModel).filter_by(code=cup).first() is not None

    def get_all_cups(self) -> list[str]:
        return [r.code.strip() for r in self.session.query(CupModel.code).all()]

    def get_all(self):
        rows = self.session.query(CupModel).all()
        return [{"id": r.id, "code": r.code.strip(), "name": r.name} for r in rows]
