import polars as pl

from src.shared.utils.company_name_normalizer import CompanyNameNormalizer


def test_clean_name_removes_suffixes():
    normalizer = CompanyNameNormalizer()
    assert normalizer._clean_name("Empresa SAS") == "EMPRESA"
    assert normalizer._clean_name("Empresa LTDA") == "EMPRESA"
    assert normalizer._clean_name("Empresa SA") == "EMPRESA"


def test_clean_name_none():
    normalizer = CompanyNameNormalizer()
    assert normalizer._clean_name(None) == ""


def test_clean_name_uppercases():
    normalizer = CompanyNameNormalizer()
    result = normalizer._clean_name("Café Ñoño")
    assert "CAFÉ" in result or "CAFE" in result


def test_normalize_dataframe():
    normalizer = CompanyNameNormalizer(score_cutoff=85, min_count=1)
    df = pl.DataFrame({
        "Empresa": ["CLINICA NORTE SAS", "CLINICA NORTE", "CLINICA NORTE LTDA", "HOSPITAL SUR"],
    })
    result = normalizer.normalize_dataframe(df, "Empresa")
    assert "Empresa_Normalizada" in result.columns
    assert result.height == 4


def test_normalize_dataframe_custom_output_column():
    normalizer = CompanyNameNormalizer(score_cutoff=85, min_count=0)
    df = pl.DataFrame({"Nombre": ["A SAS", "A SAS", "B LTDA"]})
    result = normalizer.normalize_dataframe(df, "Nombre", output_column="Normalizado")
    assert "Normalizado" in result.columns
