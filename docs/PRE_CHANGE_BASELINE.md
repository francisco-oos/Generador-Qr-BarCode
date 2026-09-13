# REPORTE PRE — Línea base antes de modificar

**Proyecto:** Server Oficina Marking Studio
**Versión inspeccionada:** 0.6.2 (base autoritativa, sin modificación alguna)
**Fecha de ejecución:** 2026-09-12
**Host de validación:** Linux x86_64, Python 3.12.3, Node.js disponible
**Propósito:** dejar constancia medible del estado PRE para poder comparar contra POST y detectar regresiones ocultas.

> Este documento describe **únicamente lo observado**. No contiene cambios ni propuestas
> aplicadas. Las decisiones de evolución van en documentos separados.

---

## 1. Integridad del paquete recibido

| Comprobación | Resultado |
|---|---|
| SHA-256 declarado | `b3c006792c7b31626ed4dfde0d842418c6e801217cb2021805a217bd18f9db4c` |
| SHA-256 recalculado sobre el ZIP entregado | **idéntico** |
| Archivos extraídos | 177 |
| Tamaño extraído | 4.6 MB |
| Basura de desarrollo (`__pycache__`, `.pytest_cache`, venv, node_modules) | **ninguna** |
| Secretos aparentes en el árbol | ninguno detectado |

El paquete está limpio y la extracción es reproducible.

---

## 2. Inventario del código fuente

### Motor (Python, `app/`)

| Archivo | Líneas aprox. | Responsabilidad observada |
|---|---:|---|
| `barcode_engine.py` | 8.7 KB | fragmentos SVG de Code 128, Code 39, QR, Data Matrix, texto; utilidades de reposicionamiento y resolución de valores |
| `template_engine.py` | 8.6 KB | `apply_input_rules` (prefijo/sufijo por modo de captura) y `render_template` (composición de la marca) |
| `batch_engine.py` | 9.8 KB | parseo CSV flexible, posiciones de slot, conciliación física, `render_batch` |
| `exporters.py` | 5.2 KB | rasterización SVG→PNG (svglib + ReportLab), manifiestos CSV/JSON, ZIP de lote y ZIP masivo |
| `code_quality.py` | 13.6 KB | preflight de legibilidad; geometría, perfil de lector, degradaciones digitales y decodificación `pyzbar` |
| `models.py` | 13.5 KB | contratos Pydantic: `TemplateSpec`, `ElementSpec`, `QualityProfile`, `JigProfile`, `MachineProfile`, `ScannerProfile`, requests de API |
| `main.py` | 31.9 KB | 30 endpoints FastAPI |
| `machine_bridge.py` | 34.6 KB | frontera con hardware: puertos, GRBL read-only `$I`/`$$`, importadores LightBurn/LaserGRBL |
| `calibration.py` | 6.5 KB | evaluación P0/PX/PY y SVG `CALIBRATION ONLY` |
| `config_loader.py` | 3.2 KB | carga de plantillas, jigs, máquinas, lectores y perfiles de calidad desde JSON |
| `db.py` | 12.0 KB | SQLite: trabajos, marcas, capturas de máquina, presets de material |
| `licensing.py` | 5.0 KB | `LicenseProvider` con firma Ed25519 |
| `material_catalog.py` | 3.1 KB | catálogo de materiales y superficies |

### Interfaz (`app/static/`)

| Archivo | Tamaño | Observación |
|---|---:|---|
| `index.html` | 30.4 KB / 390 líneas | 10 pestañas; modo guiado/experto |
| `app.js` | 69.8 KB / 559 líneas | sin framework externo; líneas muy largas y densas |
| `styles.css` | 14.9 KB / 27 líneas | CSS minificado en muy pocas líneas físicas |

### Configuración (datos, no código)

- 5 plantillas, 5 jigs, 2 máquinas, 4 lectores, 2 perfiles de calidad, 1 catálogo de materiales (23 KB).

### Documentación

24 documentos en `docs/` + `README.md` + `CHANGELOG.md`. La documentación es amplia y coherente
con el código; no se detectaron documentos huérfanos.

---

## 3. Pruebas ejecutadas SIN modificar nada

### 3.1 Suite pytest

```
59 tests recolectados · 59 PASS · 0 FAIL · tiempo total 26.66 s
```

| Archivo | Tests |
|---|---:|
| `test_machine_bridge.py` | 12 |
| `test_api.py` | 10 |
| `test_batch.py` | 5 |
| `test_ux_contract.py` | 5 |
| `test_input_rules.py` | 4 |
| `test_code_quality.py` | 3 |
| `test_config_and_render.py` | 3 |
| `test_documentation_contract.py` | 3 |
| `test_frontend_contract.py` | 3 |
| `test_material_catalog.py` | 3 |
| `test_calibration.py` | 2 |
| `test_license.py` | 2 |
| `test_machine_api.py` | 2 |
| `test_scalability.py` | 1 |
| `test_scanner_com597.py` | 1 |

**Tests más lentos (PRE):**

| Test | Segundos |
|---|---:|
| `test_batch_export_zip_and_verify` | 9.03 |
| `test_machine_import_persists_material_preset_and_batch_references_it` | 8.44 |
| `test_generate_more_than_1000_marks_without_state_leak` | 3.35 |
| `test_bulk_svg_export_1000_records_uses_same_template` | 3.23 |
| `test_all_templates_render_valid_svg_and_png` | 0.56 |

### 3.2 Warnings

Un único warning, externo al proyecto:

```
starlette/testclient.py:45 DeprecationWarning: anyio.abc.BlockingPortal alias deprecado
```

No hay warnings originados en código del proyecto.

### 3.3 Otras verificaciones

| Comprobación | Resultado |
|---|---|
| `python -m compileall app scripts tests` | **PASS** |
| `node --check app/static/app.js` | **PASS** |
| `scripts/compatibility_check.py` | **PASS** |
| Arranque real `uvicorn app.main:app` | **PASS** |
| `GET /api/health` | **200** — `version 0.6.2`, licencia válida, 5 plantillas, 2 máquinas, 5 jigs, 4 lectores |
| `GET /` (UI) | **200** |
| `direct_laser_job_streaming` | `false` (frontera de máquina respetada) |
| `grbl_read_only_probe` | `true` |

---

## 4. Rendimiento PRE (medido en este host)

Renderizado de marcas INOVA Code 128 con el motor de producción:

| Registros | Tiempo total | ms/marca | Pico de memoria | SVG generado |
|---:|---:|---:|---:|---:|
| 1 | 0.014 s | 14.36 | 0.49 MB | 0.01 MB |
| 10 | 0.081 s | 8.12 | 0.62 MB | 0.06 MB |
| 100 | 0.848 s | 8.48 | 1.78 MB | 0.65 MB |
| 1 000 | 8.938 s | 8.94 | 2.76 MB | 6.49 MB |
| 5 000 | 45.200 s | 9.04 | 2.76 MB | 32.44 MB |

**Lectura:**

- El coste por marca es **lineal y estable** (~9 ms). No hay degradación cuadrática.
- El pico de memoria **no crece** entre 1 000 y 5 000 registros: no hay fuga de estado.
- El coste absoluto es alto: **5 000 registros tardan ~45 s** y 10 000 tardarían ~90 s,
  por encima de cualquier timeout HTTP razonable de una sola petición síncrona.
  El límite declarado de 10 000 registros por solicitud es alcanzable pero incómodo.

---

## 5. Comportamiento observado del SVG generado

### 5.1 Estructura actual

```xml
<svg width="52.0000mm" height="18.0000mm" viewBox="0 0 52.0000 18.0000">
  <g id="mark">
    <svg x="6.0350" y="0.5000" width="39.93" height="10.5" viewBox="0 0 113 29" …>
      <title>…</title><desc>…</desc>
      <clipPath id="clip"><rect …/></clipPath>
      <g id="group" transform="scale(1,-1) translate(0,-29)" style="clip-path: url(#clip)">
        <g transform=""><g transform=""><rect …/> … </g></g>
      </g>
    </svg>
    …
  </g>
</svg>
```

**Observaciones de hecho:**

1. Existe **una sola capa**, `<g id="mark">`. No hay grupos semánticos
   (`layer_background`, `layer_barcode`, `layer_text`, `layer_registration`).
2. **Ningún elemento tiene un `id` estable y comprensible.** No existe `id="barcode_serial"`
   ni equivalente. Los únicos `id` presentes son `mark`, `clip` y `group`, generados por la librería.
3. Los símbolos se insertan como **`<svg>` anidados con `viewBox` propio, `clipPath` y
   `transform="scale(1,-1)"`**, no como geometría plana en milímetros del lienzo.
4. `<title>` y `<desc>` quedan como marcadores literales `…`.
5. El campo `label` de `ElementSpec` existe en el modelo pero **no se emite al SVG**.

### 5.2 Defecto reproducido: identificadores duplicados

`id` es de tipo ID en XML y debe ser único en el documento. En cuanto una plantilla
o un lote contiene más de un símbolo, el SVG generado deja de cumplirlo.

Medición sobre `samples/output/inova_batch_12.svg` (12 marcas):

```
total de id = 37
DUPLICADOS = {'mark': 12, 'clip': 12, 'group': 12}
```

Caso reproducido en el motor con dos Code 128 de longitud muy distinta:

```
anchos de clipPath en el mismo documento: ['76.3937007874016', '207.35433070866168']
IDs duplicados: {'clip': 2, 'group': 2}
```

Es decir: el documento contiene **dos `clipPath id="clip"` con geometría distinta**, y los dos
símbolos referencian `clip-path: url(#clip)`. Un renderizador conforme resuelve `url(#clip)`
contra la **primera** coincidencia del documento, de modo que el símbolo más largo queda
sujeto al recorte del más corto.

**Alcance honesto de este hallazgo:**

- Es una **violación comprobada del estándar XML/SVG**.
- **NO se reprodujo truncamiento visible con `svglib`**, el renderizador que usa la
  exportación PNG del propio proyecto. Con svglib los dos códigos se decodifican
  correctamente (`AB` y `Q00525499XYZ123456`). svglib es tolerante en este punto.
- Por tanto el riesgo es **latente**, no una falla de producción demostrada en la ruta actual.
  El riesgo se materializa en renderizadores estrictos y en cualquier flujo que reordene,
  fusione o recorte el documento.

### 5.3 CORRECCIÓN — falso positivo de rasterización con CairoSVG

> **ESTA SECCIÓN FUE CORREGIDA.** El texto original afirmaba un defecto que no existía.
> Se conserva el registro completo del error en lugar de borrarlo, porque la
> trazabilidad del análisis forma parte de la línea base.

#### Conclusión corregida

Durante la línea base se interpretó inicialmente como fallo una rasterización
aparentemente negra de CairoSVG. Posteriormente se comprobó que la causa era la
conversión incorrecta de un PNG con transparencia mediante `.convert('L')`, que
convertía píxeles transparentes en negro. Al componer correctamente sobre fondo
blanco, CairoSVG renderizaba el SVG correctamente. Por tanto, esa conclusión PRE
fue corregida y **no constituye un defecto del proyecto**.

#### Qué se afirmó y qué se midió después

| | Medición original (incorrecta) | Medición corregida |
|---|---|---|
| Método | `Image.open(png).convert("L")` | `RGBA` → `alpha_composite` sobre blanco → `L` |
| Densidad de tinta | 1.000 (imagen negra) | 0.0085 |
| Decodificación `pyzbar` | 0 códigos | código recuperado correctamente |
| Conclusión | «CairoSVG no reproduce el SVG» | CairoSVG lo reproduce bien |

CairoSVG devuelve PNG con canal alfa y fondo transparente. `convert("L")` descarta el
canal alfa, de modo que un píxel transparente `(0,0,0,0)` se convierte en luminancia `0`,
es decir, negro. El resultado era una lámina uniformemente «negra» que no correspondía a
ningún píxel realmente dibujado.

#### Consecuencia para el análisis PRE

El punto 5.2 (**identificadores duplicados**) sigue siendo válido: es una violación
comprobable del estándar XML/SVG, medida sobre el texto del archivo y por tanto ajena a
cualquier renderizador. Lo que **queda anulado** es el argumento de que la estructura
`<svg>` anidado + `clipPath` + `scale(1,-1)` fallara en un renderizador independiente.
La reestructuración del SVG se justifica por unicidad de identificadores, legibilidad de
los `id` y el ciclo de retroalimentación con Inkscape de la sección 21, **no** por una
supuesta incompatibilidad de render que nunca existió.

#### Medida preventiva adoptada

Se creó `app/raster_probe.py` como punto único de rasterización y análisis. Cualquier
validación de SVG debe pasar por él:

```text
PNG (posible RGBA) → flatten_on_white() → escala de grises → análisis / decodificación
```

Se eliminó la copia duplicada de esta lógica que existía en `tests/test_svg_structure.py`.
La suite incluye dos guardias permanentes:

- `test_flatten_on_white_is_what_prevents_the_documented_false_positive` reproduce el
  error de forma explícita: una imagen totalmente transparente da densidad 1.0 con el
  método ingenuo y 0.0 con el correcto;
- `test_no_test_measures_ink_density_on_raw_alpha` **falla** si cualquier prueba de la
  suite vuelve a usar `convert('L')` sobre una imagen con canal alfa.

### 5.4 Fortaleza del preview de lote

`samples/output/inova_batch_12_300dpi.png` decodifica **12/12** Code 128 correctos
(`Q00525499` … `Q00525510`) con `pyzbar`. La calidad del símbolo en la ruta actual es buena.

---

## 6. Calidad de la evidencia de pruebas existente

Estas observaciones son sobre **cómo se prueba**, no sobre el motor.

| Observación | Detalle |
|---|---|
| `qa_svg_interop.py` declara `inkscape: PASS` | El criterio real es «Inkscape salió con código 0 y produjo un PNG > 100 bytes». **No verifica el contenido.** Un PNG totalmente negro cumpliría ese criterio. |
| Inkscape no está disponible en este host | La ejecución previa se hizo en otro host. Aquí ese punto queda **NO PROBADO**, no PASS. |
| `qa_batch_decode.py` | Decodifica un PNG **precompilado en `samples/`**, no uno regenerado en la corrida. Valida un artefacto histórico, no la salida actual del motor. |
| `FINAL_VERIFICATION.json` | Declara `svg_interop: PASS (XML + svglib + Inkscape)`. Dado lo anterior, esa afirmación es **más fuerte que la evidencia que la respalda**. |

Ninguna de estas observaciones invalida los 59 tests PASS. Sí acotan qué significa ese PASS.

---

## 7. Auditoría de hardcode (sección 40) — estado PRE

| Ámbito | Resultado |
|---|---|
| `app/*.py` — menciones a INOVA/Sercel/Quantum/Steren/CUBOT/UMIDIGI | **2 coincidencias, ambas en comentarios/docstrings**, ninguna en lógica ejecutable |
| `app/static/app.js` | **0 coincidencias** |
| `app/static/index.html` | 4 coincidencias, todas en textos de ayuda y `placeholder` de formularios |
| Plantillas, jigs, lectores, máquinas, calidad, alias CSV, prefijos | viven en JSON, no en código |

**Conclusión PRE:** el objetivo arquitectónico de la sección 2 y la sección 40 ya está
esencialmente cumplido en el motor. El hardcode restante es copy de interfaz, no lógica.
Esto es un punto fuerte de la base y no requiere reescritura.

---

## 8. Brechas funcionales medibles frente a lo solicitado

Sólo se listan brechas **verificadas en el código**, no impresiones.

| # | Requisito solicitado | Estado PRE | Evidencia |
|---|---|---|---|
| 8, 9 | Importación **XLSX**, selector de hoja, `.xls` | **AUSENTE** | no existe `openpyxl` en `requirements.txt`; `/api/csv/inspect` sólo decodifica texto |
| 9 | Vista previa de 20–50 registros | Parcial | `preview` devuelve **20** filas fijas; no configurable |
| 18, 19 | Capas/grupos semánticos en SVG | **AUSENTE** | un único `<g id="mark">` |
| 18 | `id` estables y comprensibles por elemento | **AUSENTE** | sólo `mark`/`clip`/`group` |
| 19 | `inkscape:groupmode` / `inkscape:label` | **AUSENTE** | no aparece el namespace |
| 19, 20 | SVG maestro editable vs SVG de producción | **AUSENTE** | salida única |
| 13 | Transformaciones de datos (upper/lower/trim/padding/concat) | Parcial | `InputRule` cubre `trim`, `uppercase`, prefijo y sufijo. **Faltan** lowercase, padding con ceros y concatenación |
| 17 | Patrón de nombre `{economico}_{serial}.svg` | Parcial | `filename_field` acepta **un solo campo**, no un patrón |
| 4 | undo / redo | **AUSENTE** | 0 coincidencias en `app.js` |
| 4 | snap to grid, guías, distribución, selección múltiple, zoom, pan, copiar/pegar, z-order | **AUSENTE** | 0 coincidencias en `app.js` |
| 6 | Rotación de elementos | **AUSENTE** | no existe campo de rotación en `ElementSpec` |
| 6 | Quiet zone y «mostrar texto» por elemento | **AUSENTE** | quiet zone sólo vive en el perfil de calidad global |
| 5 | Panel de capas con ocultar/bloquear/renombrar | Parcial | existe lista de capas; **sin** visibilidad, bloqueo ni renombrado |
| 12 | Mapeo interactivo con resaltado cruzado | **AUSENTE** | el mapeo es una tabla de `select` sin vínculo visual |
| 16 | Selector de modo de salida (por registro / por jig / ambos) | Parcial | existen dos endpoints separados; no hay una elección unificada |
| 37 | Navegador de registros `1 / 1200` con primero/aleatorio/último | Parcial | hay preview del registro; sin navegación explícita |
| 22 | Reimportar ajustes desde SVG | **AUSENTE** | no existe lector de SVG; tampoco es viable hoy por falta de `id` estables |
| 39 | 10 000 registros en una petición | Declarado, **no medido aquí** | ~90 s estimados a 9 ms/marca |
| 51 | PASS real vs PASS CI vs no probado | Mezclado | ver sección 6 |

---

## 9. Puntos fuertes que NO deben tocarse

Registrado explícitamente para que la evolución no los dañe:

1. **Frontera de máquina.** `SAFE_GRBL_COMMANDS = ("$I", "$$")` con pruebas que fallan si
   aparece un comando de movimiento o potencia. `direct_laser_job_streaming: false`.
2. **Conciliación física.** Una discrepancia entre ID físico y fila bloquea la exportación.
3. **Regla de prefijos.** `manual` añade prefijo; `import` permanece `as_is` por defecto.
   Comprobado: `Q00525499` importado **no** se convierte en `Q00Q00525499`.
4. **Separación preview / producción.** Las guías del jig sólo existen en
   `preview_DO_NOT_ENGRAVE.svg`.
5. **Motor sin hardcode de fabricante.**
6. **Preflight de legibilidad** con clasificación ROBUSTO / ACEPTABLE / FRÁGIL / NO LEGIBLE.
7. **Política de materiales**: preset local validado → fabricante → investigación → Material Test.
8. **Calidad de símbolo demostrada**: 12/12 decodificaciones correctas en el lote 3×4.

Los generadores de Code 128, Code 39, QR y Data Matrix **funcionan y están probados**.
No hay evidencia que justifique sustituirlos.

---

## 10. Clasificación de resultados PRE (sección 51)

| Clase | Elementos |
|---|---|
| **PASS REAL** (ejecutado en este host) | pytest 59/59, compileall, `node --check`, `compatibility_check.py`, arranque uvicorn, `/api/health`, render SVG, rasterización svglib, decodificación pyzbar, benchmark 1–5 000 |
| **PASS CI** (declarado por el proyecto, no ejecutado aquí) | matriz Windows / macOS / Python 3.13 de `.github/workflows/ci.yml` |
| **NO PROBADO** | Inkscape (binario ausente), LightBurn, Sculpfun Space, LaserGRBL, puerto serial GRBL físico |
| **PENDIENTE FÍSICO** | grabado real sobre plástico, policarbonato, carcasa INOVA, Sercel, teléfono; foco, potencia, velocidad, contraste láser, abrasión; lectura con Steren COM-597 físico |

---

## 11. Conclusión PRE

La base 0.6.2 está **sana, limpia y verde**: 59/59 tests, arranque real correcto, sin fuga de
memoria, sin hardcode de fabricante en el motor y con una frontera de hardware bien defendida.

La evolución solicitada **no requiere reescribir el motor**. Las brechas reales se concentran en:

1. **Estructura del SVG de salida** — capas semánticas, `id` estables y unicidad de identificadores.
   Es la brecha de mayor impacto: de ella dependen las secciones 18, 19, 20, 21, 22, 23 y 49.
2. **Ingesta de datos** — XLSX, selección de hoja, vista previa configurable, transformaciones.
3. **Interacción del estudio visual** — undo/redo, snap, alineación, rotación, propiedades por elemento.
4. **Vínculo visual dato ↔ elemento** — mapeo interactivo y navegación de registros.
5. **Rigor de la evidencia de pruebas** — que un PASS signifique `INPUT == OUTPUT` verificado,
   no «el proceso salió con código 0».

## 12. Registro de correcciones a este documento

| Fecha | Sección | Cambio |
|---|---|---|
| 2026-09-12 | 5.3 | Corregida la conclusión sobre CairoSVG. Era un falso positivo por conversión de alfa con `.convert('L')`, no un defecto del proyecto. Se documenta el error, la medición correcta y la guardia añadida para impedir su reaparición. |

El resto del documento permanece como referencia para la comparación POST.
