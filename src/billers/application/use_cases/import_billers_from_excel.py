from src.billers.domain.entities.biller import Biller
from src.billers.domain.repositories.import_biller_from_excel_repository import (
    ImportBillerFromExcelRepository,
)
from src.company.domain.entities.company import Company


class ImportBillersFromExcel(ImportBillerFromExcelRepository):
    def __init__(
        self,
        biller_repo,
        company_repo,
        biller_company_repo,
        nit_service,
        progress,
        fuzz,
    ):
        self.biller_repo = biller_repo
        self.company_repo = company_repo
        self.biller_company_repo = biller_company_repo
        self.nit_service = nit_service
        self.progress = progress
        self.fuzz = fuzz

    def execute(self, df):
        self._process_billers(df)
        self._process_companies(df)

    def _process_billers(self, df):
        gestores = df["GESTOR"].drop_nulls().unique()
        catalog = self.biller_repo.all()

        with self.progress("Cargando facturadores", total=len(gestores)):
            for gestor in gestores:
                name = gestor.strip().upper()
                if name in ("NAN", "NONE"):
                    continue

                if catalog:
                    slug = self.fuzz.fuzz_property(name, catalog)
                else:
                    slug = name

                if not self.biller_repo.find_by_name(slug):
                    self.biller_repo.save(Biller(name))
                self.progress.advance()

    def _process_companies(self, df):
        rows = df.select(["NIT", "GESTOR", "EMPRESA"]).drop_nulls()

        with self.progress("Vinculando compañías", total=len(rows)):
            for row in rows.iter_rows(named=True):
                nit = row["NIT"][:9]
                gestor = row["GESTOR"]
                empresa = row["EMPRESA"]

                company = self.company_repo.find_by_nit(nit)
                if not company:
                    data = self.nit_service.search(nit)
                    name = data.name if data.name else empresa
                    company = self.company_repo.save(Company(nit, name.upper()))

                biller = self.biller_repo.find_by_name(gestor)
                if biller:
                    self.biller_company_repo.link_or_update(company[0], biller[0])
                self.progress.advance()
