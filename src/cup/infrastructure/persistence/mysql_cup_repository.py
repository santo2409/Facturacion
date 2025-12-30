from src.cup.domain.repositories.cup_repository import CupRepository
from src.shared.database.mysql_connection import get_connection


class MySQLCupRepository(CupRepository):
    def exists(self, cup: str) -> bool:
        connection = get_connection()
        cursor = connection.cursor()
        try:
            cursor.execute("SELECT 1 FROM cups WHERE code = %s LIMIT 1", (cup,))
            return cursor.fetchone() is not None
        finally:
            cursor.close()
            connection.close()

    def get_all_cups(self) -> list[str]:
        connection = get_connection()
        cursor = connection.cursor()
        try:
            cursor.execute("SELECT code FROM cups")
            return [row[0] for row in cursor.fetchall()]
        finally:
            cursor.close()
            connection.close()

    def get_all(self):
        connection = get_connection()
        cursor = connection.cursor()
        try:
            cursor.execute("SELECT id, code, name FROM cups")
            return [
                {"id": row[0], "code": row[1], "name": row[2]}
                for row in cursor.fetchall()
            ]
        finally:
            cursor.close()
            connection.close()
