# Changelog

## 0.6.2 — 2026-09-12

- Añadido preflight de legibilidad `/api/quality/check` para plantillas guardadas o borradores del diseñador.
- Clasificación por código: ROBUSTO / ACEPTABLE / FRÁGIL / NO LEGIBLE.
- Validación de módulo físico contra el perfil de calidad, límites del lienzo y simbología declarada por el lector seleccionado.
- Prueba digital opcional de rasterización + decodificación exacta bajo reducción, blur, contraste, rotación y abrasión fina.
- `pyzbar` pasa a dependencia de runtime opcional-funcional; si `libzbar` no está disponible la app continúa con análisis geométrico y lo reporta claramente.
- El lienzo visual se identifica como representación NO escaneable; la Vista real SVG se identifica como el render productivo ESCANEABLE.
- Generador individual y Estudio visual incorporan selector de lector y botón de prueba de legibilidad.
- Advertencias automáticas al usar módulos inferiores al perfil conservador.
- Documentado el riesgo de reescalado al imprimir/importar: SVG debe mantenerse a 100 % de tamaño físico.
- Añadidas pruebas unitarias/API/UX del nuevo preflight; suite total: 59 pruebas automatizadas.
- Evidencia de campo inicial: fotografía de hoja impresa decodificó `TEL-0037` (QR) y `4281847` (Code 128); confirmación de `Q00525499` queda reservada al lector físico.

## 0.6.1 — 2026-09-12

- Auditoría de mantenibilidad: comentarios `WHY:` junto a todas las funciones/clases Python y funciones JavaScript nombradas, explicando intención y límites.
- Añadida `CODE_REVIEW_GUIDE.md` con inventario de módulos, símbolos, línea y razón de existir para revisión posterior.
- Añadidas `MAINTAINER_GUIDE.md` y `UX_AND_WORKFLOW.md` con invariantes, extensión sin hardcodeo y razonamiento de interfaz.
- Interfaz reorganizada por tarea: Inicio, Operación, Diseño y Control; `Sistema` queda oculto en modo guiado.
- Nueva portada con acciones frecuentes y resumen de catálogo.
- Preview individual en vivo mientras se captura, con debounce para no saturar el backend.
- Lotes/CSV muestran stepper Datos → Mapeo → Posiciones → Salida.
- Estudio visual añade lista de capas/elementos para seleccionar objetos pequeños o superpuestos.
- QA ampliado con contratos de documentación/UX y validación visual por Chromium en el host de pruebas.

## 0.6.0 — 2026-09-12

- Replanteado el producto como **Estudio visual de marcado con plantillas**, no sólo selector de perfiles predefinidos.
- Añadido diseñador visual: crear/duplicar plantilla, agregar texto/serie, texto fijo, Code 128, Code 39, QR, Data Matrix, rectángulo y línea; arrastrar elementos y ajustar geometría en mm.
- Añadida vista real SVG en vivo usando el mismo motor de renderizado productivo mediante `/api/templates/preview`; el borrador no se persiste hasta guardarlo.
- Añadidos campos de datos configurables, identidad principal por plantilla y reglas de prefijo/sufijo aplicables al borrador.
- Eliminado del frontend el orden rígido de IDs y la tabla fija de sinónimos de CSV; los alias pasan a `metadata.csv_aliases` de cada plantilla.
- CSV ampliado con detección automática/forzada de encabezados y soporte de listas de una sola columna sin perder la primera serie.
- Cuando sólo hay una columna, se propone automáticamente para los campos de la plantilla; el mapeo continúa siendo editable.
- Añadida vista previa del primer registro CSV al cambiar el mapeo.
- Añadida exportación masiva de **un SVG por fila** hasta 10 000 registros, además del flujo por jig.
- Eliminados defaults INOVA específicos del generador de series; ahora toma campo/prefijo/sufijo desde la plantilla seleccionada.
- Mantiene el handoff seguro: Marking Studio genera arte; LightBurn/Sculpfun Space/LaserGRBL controla la máquina.
- QA ampliado a 48 pruebas automatizadas; exportación masiva validada con 1 000 y 5 000 SVG; 28/28 simulaciones de lectura y 12/12 Code 128 del jig.
- Documentación añadida/actualizada: `VISUAL_TEMPLATE_STUDIO.md`, manual rápido, arquitectura y guía CSV.

## 0.5.1 — 2026-09-12

- Identificado e incorporado el lector real Steren COM-597 visto en la fotografía.
- Perfil 1D/2D con Code 128, QR y Data Matrix; contraste documental >30 %.
- QA específico: la plantilla QR de teléfono mantiene módulo 0.50 mm (~19.7 mil), con margen sobre los 8.7 mil documentados para QR.
- Se mantiene Code 128 para nodos y QR para teléfonos; el mismo COM-597 puede verificar ambos.
- Documentado procedimiento de aceptación física específico para el lector.

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
