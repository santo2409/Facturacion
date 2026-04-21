from src.cup.domain.repositories.cup_repository import CupRepository
from src.shared.database.database import get_session
from src.shared.database.models import CupModel


class SaCupRepository(CupRepository):
    def exists(self, cup: str) -> bool:
        session = get_session()
        try:
            return session.query(CupModel).filter_by(code=cup).first() is not None
        finally:
            session.close()

    def get_all_cups(self) -> list[str]:
        session = get_session()
        try:
            return [r.code for r in session.query(CupModel.code).all()]
        finally:
            session.close()

    def get_all(self):
        session = get_session()
        try:
            rows = session.query(CupModel).all()
            return [{"id": r.id, "code": r.code, "name": r.name} for r in rows]
        finally:
            session.close()
