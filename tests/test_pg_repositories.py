"""Tests para repositorios pg_* — batch upsert con execute_values."""
import pytest
from src.rates.domain.entities.rate import Rate
from src.billers.domain.entities.biller import Biller
from src.city.domain.entities.city import City
from src.company.domain.entities.company import Company
from src.package.domain.entities.package import Package
from src.provider.domain.entities.provider import Provider
from src.special.domain.entities.special import Special
from src.company.domain.entities.company_package import CompanyPackage

from src.rates.infrastructure.persistence.pg_rates_repository import PgRatesRepository
from src.billers.infrastructure.persistence.pg_biller_repository import PgBillerRepository
from src.billers.infrastructure.persistence.pg_biller_company_repository import PgBillerCompanyRepository
from src.city.infrastructure.persistence.pg_city_repository import PgCityRepository
from src.company.infrastructure.persistence.pg_company_repository import PgCompanyRepository
from src.package.infrastructure.persistence.pg_package_repository import PgPackageRepository
from src.provider.infrastructure.persistence.pg_provider_repository import PgProviderRepository
from src.special.infrastructure.persistence.pg_special_repository import PgSpecialRepository
from src.cup.infrastructure.persistence.pg_cup_repository import PgCupRepository


# ── Helpers ──────────────────────────────────────────────────────────────────

def _clean(pg_conn, table, where="1=1"):
    with pg_conn.cursor() as cur:
        cur.execute(f"DELETE FROM {table} WHERE {where}")


# ── PgRatesRepository ───────────────────────────────────────────────────────

class TestPgRatesRepository:
    def test_save_batch_inserts(self, pg_conn):
        repo = PgRatesRepository(pg_conn)
        rates = [Rate(9999, 1, 1, 100, 1, "TestBatch")]
        _clean(pg_conn, "rates", "rateable_type = 'TestBatch'")
        count = repo.save_batch(rates)
        assert count == 1

    def test_save_batch_upsert(self, pg_conn):
        repo = PgRatesRepository(pg_conn)
        _clean(pg_conn, "rates", "rateable_type = 'TestBatch'")
        rates = [Rate(9999, 1, 1, 100, 1, "TestBatch")]
        repo.save_batch(rates)
        rates[0].rate = 200
        repo.save_batch(rates)
        row = repo.find_by_name(rates[0])
        assert row is not None and row[3] == 200


# ── PgBillerRepository ──────────────────────────────────────────────────────

class TestPgBillerRepository:
    def test_save_upsert(self, pg_conn):
        repo = PgBillerRepository(pg_conn)
        _clean(pg_conn, "billers", "name = '__TEST_BILLER__'")
        result = repo.save(Biller("__TEST_BILLER__"))
        assert result is not None
        result2 = repo.save(Biller("__TEST_BILLER__"))
        assert result2 is not None

    def test_save_batch(self, pg_conn):
        repo = PgBillerRepository(pg_conn)
        _clean(pg_conn, "billers", "name LIKE '__TBATCH_%'")
        billers = [Biller("__TBATCH_A"), Biller("__TBATCH_B")]
        results = repo.save_batch(billers)
        assert len(results) == 2


# ── PgCityRepository ────────────────────────────────────────────────────────

class TestPgCityRepository:
    def test_save_upsert(self, pg_conn):
        repo = PgCityRepository(pg_conn)
        _clean(pg_conn, "cities", "name = '__TEST_CITY__'")
        result = repo.save(City("__TEST_CITY__"))
        assert result is not None

    def test_save_batch(self, pg_conn):
        repo = PgCityRepository(pg_conn)
        _clean(pg_conn, "cities", "name LIKE '__TCITY_%'")
        cities = [City("__TCITY_A"), City("__TCITY_B")]
        results = repo.save_batch(cities)
        assert len(results) == 2


# ── PgPackageRepository ─────────────────────────────────────────────────────

class TestPgPackageRepository:
    def test_save_upsert(self, pg_conn):
        repo = PgPackageRepository(pg_conn)
        _clean(pg_conn, "packages", "name = '__TEST_PKG__'")
        result = repo.save(Package("__TEST_PKG__"))
        assert result is not None

    def test_save_batch(self, pg_conn):
        repo = PgPackageRepository(pg_conn)
        _clean(pg_conn, "packages", "name LIKE '__TPKG_%'")
        pkgs = [Package("__TPKG_A"), Package("__TPKG_B")]
        results = repo.save_batch(pkgs)
        assert len(results) == 2


# ── PgProviderRepository ────────────────────────────────────────────────────

class TestPgProviderRepository:
    def test_save_upsert(self, pg_conn):
        repo = PgProviderRepository(pg_conn)
        _clean(pg_conn, "providers", "name = '__TEST_PROV__'")
        result = repo.save(Provider("__TEST_PROV__"))
        assert result is not None

    def test_save_batch(self, pg_conn):
        repo = PgProviderRepository(pg_conn)
        _clean(pg_conn, "providers", "name LIKE '__TPROV_%'")
        provs = [Provider("__TPROV_A"), Provider("__TPROV_B")]
        results = repo.save_batch(provs)
        assert len(results) == 2


# ── PgSpecialRepository ─────────────────────────────────────────────────────

class TestPgSpecialRepository:
    def test_save_upsert(self, pg_conn):
        repo = PgSpecialRepository(pg_conn)
        _clean(pg_conn, "specials", "name = '__TEST_SPEC__'")
        result = repo.save(Special("__TEST_SPEC__"))
        assert result is not None

    def test_save_batch(self, pg_conn):
        repo = PgSpecialRepository(pg_conn)
        _clean(pg_conn, "specials", "name LIKE '__TSPEC_%'")
        specs = [Special("__TSPEC_A"), Special("__TSPEC_B")]
        results = repo.save_batch(specs)
        assert len(results) == 2


# ── PgCompanyRepository ─────────────────────────────────────────────────────

class TestPgCompanyRepository:
    def test_save_upsert(self, pg_conn):
        repo = PgCompanyRepository(pg_conn)
        _clean(pg_conn, "companies", "nit = '999999999'")
        result = repo.save(Company("999999999", "TEST_CO"))
        assert result is not None
        result2 = repo.save(Company("999999999", "TEST_CO_UPDATED"))
        assert result2 is not None

    def test_save_batch(self, pg_conn):
        repo = PgCompanyRepository(pg_conn)
        _clean(pg_conn, "companies", "nit IN ('999999998','999999997')")
        companies = [Company("999999998", "BATCH_A"), Company("999999997", "BATCH_B")]
        results = repo.save_batch(companies)
        assert len(results) == 2


# ── PgBillerCompanyRepository ───────────────────────────────────────────────

class TestPgBillerCompanyRepository:
    def test_link_or_update_batch(self, pg_conn):
        repo = PgBillerCompanyRepository(pg_conn)
        # Need valid biller and company IDs — create them first
        biller_repo = PgBillerRepository(pg_conn)
        company_repo = PgCompanyRepository(pg_conn)
        _clean(pg_conn, "companies_billers", "company_id IN (SELECT id FROM companies WHERE nit IN ('999999990','999999991'))")
        _clean(pg_conn, "companies", "nit IN ('999999990','999999991')")
        _clean(pg_conn, "billers", "name = '__TLINK_BILLER__'")

        biller = biller_repo.save(Biller("__TLINK_BILLER__"))
        c1 = company_repo.save(Company("999999990", "LINK_A"))
        c2 = company_repo.save(Company("999999991", "LINK_B"))

        pairs = [(c1[0], biller[0]), (c2[0], biller[0])]
        repo.link_or_update_batch(pairs)

        all_links = repo.all()
        linked_ids = {l["company"] for l in all_links}
        assert c1[0] in linked_ids and c2[0] in linked_ids


# ── PgCupRepository ─────────────────────────────────────────────────────────

class TestPgCupRepository:
    def test_injected_connection(self, pg_conn):
        repo = PgCupRepository(pg_conn)
        result = repo.get_all_cups()
        assert isinstance(result, list)
