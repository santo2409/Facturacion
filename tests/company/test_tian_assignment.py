from src.company.domain.entities.tian_assignment import TianAssignment


def test_construye_con_valores_por_defecto_rows_uno():
    a = TianAssignment(
        nit_original="800082633",
        name_original="LABORATORIOS DERMANAT S.A.S",
        nit_tian="900293402",
        name_final="LABORATORIOS DERMANAT S.A.S(TIAN)",
    )
    assert a.rows == 1
    assert a.nit_original == "800082633"
    assert a.nit_tian == "900293402"
    assert a.name_final == "LABORATORIOS DERMANAT S.A.S(TIAN)"


def test_acepta_rows_explicito():
    a = TianAssignment(
        nit_original="1",
        name_original="X",
        nit_tian="900293402",
        name_final="X(TIAN)",
        rows=3,
    )
    assert a.rows == 3
