from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    ForeignKey,
    Integer,
    String,
    TIMESTAMP,
    UniqueConstraint,
)
from sqlalchemy.sql import func

from src.shared.database.database import Base


class TypeActivityModel(Base):
    __tablename__ = "type_activities"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(10), nullable=False, unique=True, server_default="INTRA")
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now())

    __table_args__ = (CheckConstraint("name IN ('INTRA', 'EXTRA')"),)


class CupModel(Base):
    __tablename__ = "cups"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(9), nullable=False, unique=True)
    name = Column(String(255), nullable=False, unique=True)
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now())


class ImedicalModel(Base):
    __tablename__ = "imedical"

    nit_error = Column(String(50), nullable=False, primary_key=True)
    name = Column(String(255), nullable=False)
    nit_success = Column(String(12), nullable=False)
    name_error = Column(String(255), nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now())
    deleted_at = Column(TIMESTAMP, nullable=True)


class RateModel(Base):
    __tablename__ = "rates"

    rateable_id = Column(Integer, nullable=False, primary_key=True)
    city_id = Column(Integer, nullable=False, primary_key=True)
    cup_id = Column(Integer, nullable=False, primary_key=True)
    rate = Column(BigInteger, nullable=False)
    activity_id = Column(Integer, nullable=False, primary_key=True)
    rateable_type = Column(String(200), nullable=False, primary_key=True)
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now())


class BillerModel(Base):
    __tablename__ = "billers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False, unique=True)
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now())


class CityModel(Base):
    __tablename__ = "cities"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False, unique=True)
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now())


class PackageModel(Base):
    __tablename__ = "packages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False, unique=True)
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now())


class ProviderModel(Base):
    __tablename__ = "providers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False, unique=True)
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now())


class SpecialModel(Base):
    __tablename__ = "specials"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False, unique=True)
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now())


class TianModel(Base):
    __tablename__ = "tian"

    nit_error = Column(String(50), nullable=False, primary_key=True, unique=True)
    name = Column(String(255), nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now())


class CompanyModel(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    nit = Column(String(12), nullable=False, unique=True)
    name = Column(String(255), nullable=False)
    verified_at = Column(TIMESTAMP, nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now())


class CompanyBillerModel(Base):
    __tablename__ = "companies_billers"

    biller_id = Column(Integer, nullable=False, primary_key=True)
    company_id = Column(
        Integer,
        ForeignKey("companies.id"),
        nullable=False,
        primary_key=True,
        unique=True,
    )
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now())


class CompanyPackageModel(Base):
    __tablename__ = "companies_packages"

    company_id = Column(
        Integer,
        ForeignKey("companies.id"),
        nullable=False,
        primary_key=True,
    )
    package_id = Column(Integer, nullable=False, primary_key=True)
    model = Column(String(60), nullable=False, primary_key=True)
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now())

    __table_args__ = (UniqueConstraint("company_id"),)
