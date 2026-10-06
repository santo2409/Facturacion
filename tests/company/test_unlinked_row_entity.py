from src.company.domain.entities.unlinked_row import UnlinkedRow


def test_unlinked_row_construccion_y_campos():
    row = UnlinkedRow(
        document="900111111",
        company_name="EMPRESA A",
        package="PAQUETE BASICO",
        reason="Empresa no encontrada en la base de datos",
    )
    assert row.document == "900111111"
    assert row.company_name == "EMPRESA A"
    assert row.package == "PAQUETE BASICO"
    assert row.reason == "Empresa no encontrada en la base de datos"
