"""AUD-64: el .env se carga una sola vez por proceso, con override como antes."""

from src.shared import env


def _env_temporal(tmp_path, contenido: str):
    ruta = tmp_path / ".env"
    ruta.write_text(contenido, encoding="utf-8")
    return ruta


def test_load_env_overrides_system_variable(tmp_path, monkeypatch):
    monkeypatch.setattr(env, "_loaded", False)
    monkeypatch.setenv("GOLDEN_ENV_PRUEBA", "del-sistema")
    ruta = _env_temporal(tmp_path, "GOLDEN_ENV_PRUEBA=del-archivo\n")

    env.load_env(ruta)

    import os
    assert os.environ["GOLDEN_ENV_PRUEBA"] == "del-archivo"


def test_load_env_reads_file_only_once(tmp_path, monkeypatch):
    import os

    monkeypatch.setattr(env, "_loaded", False)
    monkeypatch.delenv("GOLDEN_ENV_PRUEBA", raising=False)
    ruta = _env_temporal(tmp_path, "GOLDEN_ENV_PRUEBA=primera\n")

    env.load_env(ruta)
    monkeypatch.setenv("GOLDEN_ENV_PRUEBA", "cambiada-despues")
    env.load_env(ruta)  # segunda llamada: no vuelve a pisar el entorno

    assert os.environ["GOLDEN_ENV_PRUEBA"] == "cambiada-despues"
