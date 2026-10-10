# ADR-004: Playwright para Web Scraping del RUES

## Estado
Aceptado

## Fecha
2024-12-14

## Contexto

El sistema necesita validar NITs de empresas consultando el RUES (Registro Único Empresarial y Social de Colombia). El sitio web del RUES:
- Requiere interacción con JavaScript (SPA)
- Presenta modales que deben cerrarse programáticamente
- No expone una API pública
- Usa formularios dinámicos con búsqueda asíncrona

Alternativas evaluadas:
1. Selenium + ChromeDriver
2. Playwright (Firefox headless)
3. Requests + BeautifulSoup (solo HTTP)
4. API de datos.gov.co

## Decisión

Se adopta **Playwright con Firefox headless** para el scraping del RUES:
- Ejecución asíncrona (`async_playwright`) envuelta en `asyncio.run()`
- Firefox como navegador (menor detección como bot)
- BeautifulSoup para parsing del HTML resultante
- Manejo de timeouts y errores con reintentos implícitos

## Consecuencias

### Positivas
- Manejo nativo de JavaScript y SPAs
- API asíncrona de alto nivel
- Menor tasa de bloqueo que Selenium/Chrome
- Instalación simple (`playwright install firefox`)
- Soporte para esperas explícitas (`wait_for`)

### Negativas
- Dependencia pesada (~200MB para el navegador)
- Velocidad limitada por la latencia del sitio web
- Fragilidad ante cambios en la estructura HTML del RUES
- Uso de XPath hardcodeado para localizar elementos

## Notas
Se mantiene `datos_gov_scraper.py` como alternativa para consultas que no requieren JavaScript. El scraper implementa el patrón Repository (`NitScraperRepository`) permitiendo intercambiar implementaciones.

> **Actualización (spec 014, 2026-10-10):** `datos_gov_scraper.py` se eliminó: nunca participó en la cascada de búsqueda (BD → Odoo → RUES) y no implementaba `search_by_name`. El patrón Repository sigue vigente con `NitScraperRepository` y `RuesPlaywrightScraper`. El texto de arriba se conserva como historia.
