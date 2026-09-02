# Plan 001 — Aclarar prompts de ruta de archivo en "Asignar Tarifas"

## Diseño técnico

### 1. `src/shared/console/file_input.py`

Añadir parámetro opcional `label` con el texto actual como default, para no afectar las 5 llamadas existentes que no lo necesitan:

```python
def ask_excel_path(label: str = "Ruta completa del archivo Excel") -> Path:
    while True:
        path = Prompt.ask(label)
        file = Path(path)

        if file.exists() and file.suffix in (".xlsx", ".xls"):
            return file

        console.print("Archivo inválido, intente de nuevo")
```

### 2. `src/assign/infrastructure/console/assigned_rates_controller.py`

- Línea 53: `path = ask_excel_path("Ruta del Excel de TARIFAS (consolidado)")`
- Línea 60: `facture_path = ask_excel_path("Ruta del Excel con NÚMEROS DE FACTURA")`

Los comentarios existentes (`# Libro consolidado (tarifas)` / `# Libro de facturas...`) se conservan.

### 3. Test

Nuevo archivo `tests/shared/test_file_input.py`, siguiendo el patrón de mock usado en `tests/shared/test_rich_progress.py` (mock de `rich.prompt.Prompt.ask` vía `unittest.mock.patch`, ya que es una dependencia externa de UI, no un repositorio de dominio — no aplica el patrón de fakes manuales).

Casos:
- `ask_excel_path()` sin argumento muestra el texto default y retorna la ruta si el archivo existe y tiene extensión válida.
- `ask_excel_path(label="mi label")` muestra ese texto exacto en el prompt (`Prompt.ask` se llama con `"mi label"`).

## Archivos afectados

- `src/shared/console/file_input.py` (modificado)
- `src/assign/infrastructure/console/assigned_rates_controller.py` (modificado, 2 líneas)
- `tests/shared/test_file_input.py` (nuevo)

## Verificación

1. `pytest tests/shared/test_file_input.py -v` → verde.
2. `pytest tests/assign/ -v` → sigue en verde (no debería haber tests que dependan del texto del prompt, pero se confirma que nada se rompe).
3. Inspección manual del diff: confirmar que las 5 llamadas restantes a `ask_excel_path()` no pasan `label` y por tanto conservan el texto original.
