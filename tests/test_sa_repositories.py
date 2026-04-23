"""Tests para repositorios sa_* — bulk upsert con SQLAlchemy."""
import pytest
from sqlalchemy import text

from src.rates.domain.entities.rate import Rate
from src.billers.domain.entities.biller import Biller
from src.city.domain.entities.city import City
from src.company.domain.entities.company import Company
from src.package.domain.entities.package import Package
from src.provider.domain.entities.provider import Provider
from src.special.domain.entities.special import Special

from src.rates.infrastructure.persistence.sa_rates_repository import SaRatesRepository
from src.billers.infrastructure.persistence.sa_biller_repository import SaBillerRepository
from src.billers.infrastructure.persistence.sa_biller_company_repository import SaBillerCompanyRepository
from src.city.infrastructure.persistence.sa_city_repository import SaCityRepository
from src.company.infrastructure.persistence.sa_company_repository import SaCompanyRepository
from src.package.infrastructure.persistence.sa_package_repository import SaPackageRepository
from src.provider.infrastructure.persistence.sa_provider_repository import SaProviderRepository
from src.special.infrastructure.persistence.sa_special_repository import SaSpecialRepository
from src.cup.infrastructure.persistence.sa_cup_repository import SaCupRepository


def _clean(session, table, where="1=1"):
    session.execute(text(f"DELETE FROM {table} WHERE {where}"))
    session.flush()


class TestSaRatesRepository:
    def test_save_batch_upsert(self, sa_session):
        repo = SaRatesRepository(sa_session)
        _clean(sa_session, "rates", "rateable_type = 'TestBatch'")
        rates = [Rate(9999, 1, 1, 100, 1, "TestBatch")]
        count = repo.save_batch(rates)
        assert count == 1
        rates[0].rate = 200
        repo.save_batch(rates)
        row = repo.find_by_name(rates[0])
        assert row is not None and row[3] == 200


class TestSaBillerRepository:
    def test_save_batch(self, sa_session):
        repo = SaBillerRepository(sa_session)
        _clean(sa_session, "billers", "name LIKE '__TSAB_%'")
        billers = [Biller("__TSAB_A"), Biller("__TSAB_B")]
        results = repo.save_batch(billers)
        assert len(results) == 2


class TestSaCityRepository:
    def test_save_batch(self, sa_session):
        repo = SaCityRepository(sa_session)
        _clean(sa_session, "cities", "name LIKE '__TSAC_%'")
        cities = [City("__TSAC_A"), City("__TSAC_B")]
        results = repo.save_batch(cities)
        assert len(results) == 2


class TestSaPackageRepository:
    def test_save_batch(self, sa_session):
        repo = SaPackageRepository(sa_session)
        _clean(sa_session, "packages", "name LIKE '__TSAP_%'")
        pkgs = [Package("__TSAP_A"), Package("__TSAP_B")]
        results = repo.save_batch(pkgs)
        assert len(results) == 2


class TestSaProviderRepository:
    def test_save_batch(self, sa_session):
        repo = SaProviderRepository(sa_session)
        _clean(sa_session, "providers", "name LIKE '__TSAPROV_%'")
        provs = [Provider("__TSAPROV_A"), Provider("__TSAPROV_B")]
        results = repo.save_batch(provs)
        assert len(results) == 2


class TestSaSpecialRepository:
    def test_save_batch(self, sa_session):
        repo = SaSpecialRepository(sa_session)
        _clean(sa_session, "specials", "name LIKE '__TSASPEC_%'")
        specs = [Special("__TSASPEC_A"), Special("__TSASPEC_B")]
        results = repo.save_batch(specs)
        assert len(results) == 2


class TestSaCompanyRepository:
    def test_save_batch(self, sa_session):
        repo = SaCompanyRepository(sa_session)
        _clean(sa_session, "companies", "nit IN ('999999998','999999997')")
        companies = [Company("999999998", "SA_BATCH_A"), Company("999999997", "SA_BATCH_B")]
        results = repo.save_batch(companies)
        assert len(results) == 2


class TestSaBillerCompanyRepository:
    def test_link_or_update_batch(self, sa_session):
        biller_repo = SaBillerRepository(sa_session)
        company_repo = SaCompanyRepository(sa_session)
        repo = SaBillerCompanyRepository(sa_session)

        _clean(sa_session, "companies_billers", "company_id IN (SELECT id FROM companies WHERE nit IN ('999999990','999999991'))")
        _clean(sa_session, "companies", "nit IN ('999999990','999999991')")
        _clean(sa_session, "billers", "name = '__TSALINK__'")
        sa_session.commit()

        biller = biller_repo.save(Biller("__TSALINK__"))
        c1 = company_repo.save(Company("999999990", "SA_LINK_A"))
        c2 = company_repo.save(Company("999999991", "SA_LINK_B"))

        pairs = [(c1[0], biller[0]), (c2[0], biller[0])]
        repo.link_or_update_batch(pairs)

        # Verify with direct SQL to avoid session cache issues
        from sqlalchemy import text
        rows = sa_session.execute(
            text("SELECT company_id FROM companies_billers WHERE company_id IN (:c1, :c2)"),
            {"c1": c1[0], "c2": c2[0]}
        ).fetchall()
        linked_ids = {r[0] for r in rows}
        assert c1[0] in linked_ids and c2[0] in linked_ids


class TestSaCupRepository:
    def test_injected_session(self, sa_session):
        repo = SaCupRepository(sa_session)
        result = repo.get_all_cups()
        assert isinstance(result, list)
