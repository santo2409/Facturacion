"""La documentación describe el esquema vigente de salida al usuario (spec 011, AC-12).

Son pruebas de contenido sobre los .md del repositorio: `user_audit.xlsx` y el
"logging dual" solo pueden aparecer como historia explícita (ADR reemplazados)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ADR = ROOT / "docs" / "adr"


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_new_adr_exists_and_old_ones_are_marked_replaced():
    adr14 = ADR / "ADR-014-salida-consola-y-libros-por-ejecucion.md"
    assert adr14.exists()
    text = adr14.read_text(encoding="utf-8")
    assert "## Estado" in text and "Aceptado" in text
    assert "ADR-008" in text and "ADR-011" in text
    assert "FindingsWriter" in text and "logs/<opcion>/<AAAA-MM-DD_HHMM>/" in text

    for old in ("ADR-008-logging-dual.md", "ADR-011-excel-audit-handler.md"):
        old_text = (ADR / old).read_text(encoding="utf-8")
        assert "Reemplazado por [ADR-014]" in old_text
        assert "ADR-014-salida-consola-y-libros-por-ejecucion.md" in old_text

    index = (ADR / "README.md").read_text(encoding="utf-8")
    assert "ADR-014-salida-consola-y-libros-por-ejecucion.md" in index
    for row in (line for line in index.splitlines() if line.startswith(("| [ADR-008]", "| [ADR-011]"))):
        assert "Reemplazado" in row


_RULE_FILES = [
    "CLAUDE.md",
    ".claude/rules/structure.md",
    ".claude/rules/tech.md",
    ".claude/rules/product.md",
]
_STALE_TERMS = ("user_audit", "ExcelAuditHandler", "excel_audit_handler", "Logging dual", "Auditoría dual", "dual logging")


def test_project_rules_do_not_describe_user_audit_as_current():
    offenders = [
        f"{name}: {term}"
        for name in _RULE_FILES
        for term in _STALE_TERMS
        if term.lower() in _read(name).lower()
    ]

    assert offenders == []


def test_project_rules_describe_the_current_output_scheme():
    claude = _read("CLAUDE.md")
    assert "Salida al usuario" in claude
    assert "FindingsWriter" in claude and "USER_CONSOLE" in claude

    structure = _read(".claude/rules/structure.md")
    assert "user_console.py" in structure and "xlsx_findings_writer.py" in structure
    assert "logs/<opcion>/<AAAA-MM-DD_HHMM>/" in structure

    assert "RichHandler" in _read(".claude/rules/tech.md")
    assert "Hallazgos por ejecución" in _read(".claude/rules/product.md")


_USER_DOCS = [
    "README.md",
    "docs/USER_GUIDE.md",
    "docs/TECHNICAL_DOCUMENTATION.md",
    "docs/c4-diagrams.md",
]


def test_user_docs_do_not_describe_user_audit_as_current():
    offenders = [
        f"{name}: {term}"
        for name in _USER_DOCS
        for term in ("user_audit", "ExcelAuditHandler", "Logging dual", "log de auditoría")
        if term.lower() in _read(name).lower()
    ]

    assert offenders == []


def test_user_docs_describe_findings_folders():
    guide = _read("docs/USER_GUIDE.md")
    for folder in ("logs/facturadores", "logs/asignar_tarifas"):
        assert folder in guide

    technical = _read("docs/TECHNICAL_DOCUMENTATION.md")
    assert "ADR-014" in technical and "FindingsWriter" in technical and "USER_CONSOLE" in technical
    assert "ADR-014" in _read("README.md") or "consola" in _read("README.md").lower()


def test_user_guide_explains_vinculacion_duplicada_columns():
    """spec 015, NF-03: el libro indica el facturador descartado y el vigente."""
    guide = _read("docs/USER_GUIDE.md")
    row = next(l for l in guide.splitlines() if l.startswith("| `logs/facturadores/`"))

    assert "vinculacion_duplicada" in row
    assert "descartado" in row and "vigente" in row


# ── spec 016: Odoo es la fuente de verdad en la validación de empresas ─────

def _mermaid_block_after(text: str, heading: str) -> str:
    start = text.index(heading)
    block_start = text.index("```mermaid", start)
    return text[block_start : text.index("```", block_start + 10)]


def test_c4_company_cascade_starts_with_odoo():
    block = _mermaid_block_after(
        _read("docs/c4-diagrams.md"), "## Flujo: Cascada de validación de empresas (opción 1)"
    )
    first_step = block[block.index("START"):]
    odoo_nit = first_step.index("Odoo por NIT")
    odoo_name = first_step.index("Odoo por nombre")
    local_nit = first_step.index("BD local por NIT")
    local_name = first_step.index("BD local por nombre")

    assert odoo_nit < odoo_name < local_nit < local_name
    assert "Odoo no disponible" in block and "bd_local_actualizada" in block


def test_c4_cascade_note_says_odoo_is_the_source_of_truth():
    c4 = _read("docs/c4-diagrams.md")
    section = c4[c4.index("## Flujo: Cascada de validación de empresas (opción 1)"):]
    section = section[: section.index("## Flujo: Pipeline de Asignar Tarifas")]

    assert "fuente de verdad" in section


def test_technical_doc_describes_odoo_first_order_and_the_new_book():
    technical = _read("docs/TECHNICAL_DOCUMENTATION.md")
    section = technical[technical.index("### 7.1 "):technical.index("### 7.2 ")]
    odoo_row = section.index("| 1 | Odoo")
    local_row = section.index("| 3 | BD local")

    assert odoo_row < local_row
    assert "bd_local_actualizada" in technical and "logs/web_scrapping" in technical
    assert "rues_cache" in section or "caché de RUES" in section


def test_user_guide_describes_odoo_first_and_bd_local_actualizada_book():
    guide = _read("docs/USER_GUIDE.md")
    option1 = guide[guide.index("### Opción 1 — Web Scrapping"):guide.index("### Opción 2 — Facturadores")]

    assert option1.index("Odoo") < option1.index("base de datos local")
    assert "bd_local_actualizada" in guide
    assert "Odoo no disponible" in guide


def test_user_guide_lists_logs_web_scrapping_folder():
    guide = _read("docs/USER_GUIDE.md")
    row = next(l for l in guide.splitlines() if l.startswith("| `logs/web_scrapping/`"))

    assert "bd_local_actualizada" in row
