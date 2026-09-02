# Tasks 001 — Aclarar prompts de ruta de archivo en "Asignar Tarifas"

- [x] 1. Escribir `tests/shared/test_file_input.py` con los dos casos (default label / label explícito). Ejecutar `pytest tests/shared/test_file_input.py -v` y confirmar que falla (rojo) porque `ask_excel_path` aún no acepta `label`.
- [x] 2. Modificar `src/shared/console/file_input.py` para aceptar el parámetro opcional `label`.
- [x] 3. Ejecutar `pytest tests/shared/test_file_input.py -v` de nuevo y confirmar verde.
- [x] 4. Modificar `src/assign/infrastructure/console/assigned_rates_controller.py` líneas 53 y 60 para pasar los textos distintivos.
- [x] 5. Ejecutar `pytest tests/assign/ -v` completo y confirmar que sigue en verde.
- [x] 6. Ejecutar `pytest` (suite completa) para confirmar que no se rompió nada más — 306 passed.
