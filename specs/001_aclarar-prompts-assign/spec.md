# Spec 001 — Aclarar prompts de ruta de archivo en "Asignar Tarifas"

## Qué se construye

En la opción 6 del menú CLI ("Asignar Tarifas"), cuando el día del mes está fuera del rango válido (`DAY_INITIAL`/`DAY_FINAL`), el flujo pide al usuario dos rutas de archivo Excel consecutivas usando el mismo texto de prompt (`"Ruta completa del archivo Excel"`), sin indicar cuál de los dos archivos se está solicitando en cada caso.

Se debe diferenciar el texto de cada prompt para que el usuario sepa, sin ambigüedad, si se le pide:
1. El Excel de **tarifas** (consolidado de entrada, usado para asignar tarifas).
2. El Excel con **números de factura** (columnas `N° Identificación` y `# FACTURA`, usado para enriquecer el resultado).

## Por qué

El usuario reportó confusión real al usar la opción 6: no sabe cuál archivo debe seleccionar en cada prompt porque el texto es idéntico en ambos casos. La distinción hoy solo existe como comentario en el código (invisible en consola).

## Alcance

- Únicamente se ajusta el texto mostrado en los dos prompts de `assigned_rates_controller.py` que llaman a `ask_excel_path()`.
- Se añade un parámetro opcional a `ask_excel_path()` para permitir pasar un texto distinto, preservando el comportamiento por defecto para las demás 5 llamadas existentes en el proyecto.

## Fuera de alcance

- No se modifica la cascada de asignación de tarifas (7 fases).
- No se modifica la generación de `CONSOLIDADO.xlsx` ni ningún otro archivo de salida.
- No se tocan los otros controllers que usan `ask_excel_path()` sin ambigüedad (`missing_rates_controller.py`, `import_billers_controller.py`, `import_rates_controller.py`, `import_information_controller.py`, `import_companies_rates_controller.py`).
- No se añaden nuevas validaciones de columnas ni de contenido de los archivos.

## Alineación con la constitución

- **Simplicidad**: cambio mínimo, un parámetro opcional con default, sin nuevas dependencias.
- **Spec manda**: este documento delimita exactamente el cambio; cualquier ampliación de alcance requiere una nueva spec.
- **Lógica separada**: el cambio queda en `infrastructure/console` (capa de presentación CLI), no toca `domain` ni `application`.
- **Test**: se añade/ajusta test unitario sobre `ask_excel_path()` para cubrir el parámetro `label` (rojo → verde).
- **Idioma**: los mensajes al usuario quedan en español; el código (nombres de parámetros, etc.) en inglés.
