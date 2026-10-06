"""Tests de contrato ABC para CompanyRepository (spec 007, hallazgo H-16:
RF-10 a RF-12). Antes de esta spec no existía en el repositorio ningún
test de contrato (`issubclass`/`__abstractmethods__`); este archivo es el
primero."""

import pytest

from src.company.domain.repositories.company_repository import CompanyRepository
from src.company.infrastructure.persistence.sa_company_repository import (
    SaCompanyRepository,
)
from tests.fakes.fake_company_repo import FakeCompanyRepo


def test_sa_company_repository_es_subclase_de_company_repository():
    assert issubclass(SaCompanyRepository, CompanyRepository)
    SaCompanyRepository(session=None, logger=None)  # se instancia sin error


def test_fake_company_repo_es_subclase_de_company_repository():
    assert issubclass(FakeCompanyRepo, CompanyRepository)
    FakeCompanyRepo()  # se instancia sin error


def test_implementacion_incompleta_no_se_puede_instanciar():
    class RepoIncompleto(CompanyRepository):
        def find_by_nit(self, nit):
            return None

        def save(self, company):
            return None

        def save_batch(self, companies):
            return []

        def find_by_name(self, name):
            return None

        def all(self):
            return []

        # falta companies_packages_all y companies_packages_batch

    with pytest.raises(TypeError):
        RepoIncompleto()


def test_company_repository_declara_companies_packages_all_y_batch():
    assert "companies_packages_all" in CompanyRepository.__abstractmethods__
    assert "companies_packages_batch" in CompanyRepository.__abstractmethods__
