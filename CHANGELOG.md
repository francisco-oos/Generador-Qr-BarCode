# Changelog

## 0.5.0 — 2026-09-12

- Añadidos modos **Guiado** y **Experto**.
- Añadida calibración de jig P0/PX/PY, SVG de referencia y evaluación de traslación/escala/escuadra.
- Corregida la referencia de foco S9 Pro a **50 mm** según el manual oficial revisado.
- Añadido handoff/documentación de Sculpfun Space.
- Añadida captura manual de presets ya validados por el área.
- Añadida detección/importación read-only de bases de materiales LaserGRBL `.psh`.
- Ampliada detección/importación LightBurn y documentación de Material Test.
- Ampliadas pruebas CSV, calibración, API, SVG/Inkscape, browser-fallback y compatibilidad.
- Añadida prueba HTTP multipart con CSV real de 1,200 registros y QA independiente 4/4 de importadores `.clb`, `.lbmt`, `.psh` y dump GRBL.
- SVG de calibración validado además por XML, svglib e Inkscape, separado explícitamente de las salidas productivas.
- Añadidos `MANUAL_RAPIDO.md`, `CALIBRATION_AND_ALIGNMENT.md` y `SOFTWARE_HANDOFF_AND_MACHINE_SETTINGS.md`.

## 0.4.0 — 2026-09-12

- Añadida biblioteca de referencias de materiales separada de los presets productivos del taller.
- Añadidas fichas de riesgo para PVC/vinilo, ABS, policarbonato, goma desconocida y composites de fibra de vidrio sin resina identificada; no se generan presets productivos para ellos.
- Añadidas referencias iniciales de superficies para CUBOT KingKong 9, UMIDIGI BISON X10/X10 Pro y Xiaomi/Redmi.
- Añadida UI **Materiales / Presets** con buscador de materiales y consulta de modelos de teléfono.
- Añadido parser de LightBurn Material Test `.lbmt` y preferencias `.lbprefs`/`prefs.ini`.
- Añadida detección local read-only de artefactos LightBurn en rutas convencionales de Windows/Linux/macOS, con importación restringida a archivos previamente detectados.
- Conservada importación por archivo para escenarios donde LightBurn está en otra PC y Marking Studio corre en Server Oficina/Linux.
- UI de Sistema actualizada para detectar/importar ajustes ya descubiertos por el área.
- Compatibilidad ampliada a `.lbmt`, `.lbprefs` y `prefs.ini` sin modificar LightBurn ni el controlador.
- QA ampliado para catálogo de materiales, teléfonos, rutas multiplataforma y seguridad de discovery local.
- Documentación ampliada sobre presets, materiales, teléfonos ensamblados, seguridad, portabilidad e interoperabilidad.

## 0.3.0 — 2026-09-12

- Añadido asistente de prefijo/sufijo por campo y distinción manual vs importación.
- INOVA permite escribir `525499` manualmente y resolver `Q00525499`; CSV se conserva as-is por defecto.
- Añadido `machine_bridge.py` para importación segura de `.clb`, `.lbset`, `.lbrn/.lbrn2`, `.lbzip/.zip` y dumps GRBL.
- Añadida lectura GRBL opcional limitada a `$I` y `$$`; sin movimientos, potencia, homing ni escrituras de settings.
- Añadidos SHA-256, copia local de exports de configuración e histórico de capturas/presets.
- Presets importados pueden asociarse a un lote y quedan registrados en `job.json`.
- Diagnóstico no destructivo de límites `$130/$131` y `$32` frente al perfil configurado.
- Añadidos launchers macOS y comprobación de Python >=3.12 en Linux/macOS/Windows.
- Añadida matriz CI Windows/Linux/macOS × Python 3.12/3.13.
- Añadidas pruebas de parsers, prefijos, API, preset/material y serial read-only.
- Añadido simulador PTY GRBL de extremo a extremo para Linux/POSIX.
- Documentación ampliada: problema/propuesta, captura de ajustes del taller, interoperabilidad y matriz de compatibilidad.
- Incluido render conceptual de la solución en `docs/media/`.

## 0.2.0 — 2026-09-11

- Plantillas INOVA/Sercel/teléfono/genérico.
- CSV, series, jigs, conciliación física, histórico y verificación de escaneo.
- Licencia standalone Ed25519 y frontera de integración con Server Oficina.
- QA de lectura digital y benchmark >1,000 registros.
