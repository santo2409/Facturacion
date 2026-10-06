from src.company.domain.entities.imedical_correction import ImedicalCorrection


def test_construye_con_los_cuatro_campos():
    c = ImedicalCorrection(
        nit_error="1015426422",
        nit_success="860504759",
        name="FUNDACION UNIVERSITARIA KONRAD LORENZ",
        name_error="FUND KONRAD LORENZ",
    )
    assert c.nit_error == "1015426422"
    assert c.nit_success == "860504759"
    assert c.name == "FUNDACION UNIVERSITARIA KONRAD LORENZ"
    assert c.name_error == "FUND KONRAD LORENZ"


def test_name_error_es_opcional_por_defecto_none():
    c = ImedicalCorrection(nit_error="191461130", nit_success="19146113", name="X")
    assert c.name_error is None
